import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, NextTimeStep
from typing import List, Tuple

# Для раннера
import os
from pathlib import Path
from cocotb_test.simulator import run 

# Период тактового сигнала в наносекундах
CLK_PERIOD = 10 

# ==============================================================================
# Helper Functions
# ==============================================================================

async def reset_dut(dut, enable=True):
    """Сброс DUT и ожидание стабильности, установка EN."""
    dut["in"].value = 0
    dut.rst.value = 1
    
    # Установка EN в 1, если не требуется иное
    if enable:
        dut.en.value = 1
    
    clk_period = CLK_PERIOD
    await Timer(clk_period, units="ns")
    await RisingEdge(dut.clk)
    
    dut.rst.value = 0
    await RisingEdge(dut.clk)
    
    assert dut.detector_out.value == 0, "Reset failed: detector_out should be 0"
    dut._log.info(f"DUT initialized and rst deasserted. State: S0. EN={dut.en.value}")

async def execute_sequence(dut, sequence: str, expected_outputs: str):
    """Подаёт последовательность входных данных (in) и проверяет выход (detector_out)."""
    assert len(sequence) == len(expected_outputs), "Sequence and expected output lengths must match."
    
    for i, (input_bit, expected_out) in enumerate(zip(sequence, expected_outputs)):
        input_val = int(input_bit)
        expected_val = int(expected_out)
        
        dut["in"].value = input_val
        
        await Timer(CLK_PERIOD // 2, units='ns')
        await RisingEdge(dut.clk)
        await NextTimeStep() 
        
        current_out = int(dut.detector_out.value)
        
        dut._log.info(
            f"Step {i+1} (In={input_val}): Expected Out={expected_val}, Actual Out={current_out}"
        )
        
        assert current_out == expected_val, \
            f"Mismatch at step {i+1}: Input='{sequence[:i+1]}'. Expected Out={expected_val}, Actual Out={current_out}"

# ==============================================================================
# Tests
# ==============================================================================

@cocotb.test()
async def test_sequence_detector_1101101(dut):
    """Проверка основных сценариев для детектора последовательности 1101101."""
    
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD, units="ns").start())
    
    dut._log.info("--- Начинаем проверку FSM 1101101 ---")

    # --- Сценарий 1: Успешное обнаружение 1101101 (Базовый) ---
    seq_full = "1101101"
    exp_full = "0000001"
    
    dut._log.info(f"\nТест 1: Полная последовательность: {seq_full}")
    await reset_dut(dut)
    await execute_sequence(dut, seq_full, exp_full)

    # --- Сценарий 2: Перекрывающиеся последовательности (1101101 + 10) ---
    # Переход: S7(1) -> S2 (11), S2(0) -> S3 (110)
    seq_overlap = "110110101101" 
    exp_overlap = "000000100001" # 1101101 (Out=1) -> 101101 (Out=1)
    
    dut._log.info(f"\nТест 2: Перекрытие (1101101101)")
    await reset_dut(dut)
    await execute_sequence(dut, seq_overlap, exp_overlap)

    # --- Сценарий 3: Ложный старт (10 -> Сброс) ---
    # Sequence: 10110100
    # States:   S1 S0 S1 S2 S3 S0 S0
    # Output:   0 0 0 0 0 0 0 0
    seq_false = "10110100"
    exp_false = "00000000"
    
    dut._log.info(f"\nТест 3: Ложный старт (10 -> Сброс)")
    await reset_dut(dut)
    await execute_sequence(dut, seq_false, exp_false)
    
    # --- Сценарий 4: Максимальный сброс (11010) ---
    # В S4 (1101) приходит 0, что должно сбросить FSM в S0
    # Sequence: 1   1   0   1   0
    # States:   S1  S2  S3  S4  S0
    # Output:   0   0   0   0   0
    seq_max_reset = "11010"
    exp_max_reset = "00000"
    
    dut._log.info(f"\nТест 4: Максимальный сброс (11010)")
    await reset_dut(dut)
    await execute_sequence(dut, seq_max_reset, exp_max_reset)


    # --- Сценарий 5: Проверка EN=0 (Пауза) ---
    # Дойдем до S5 (11011), затем EN=0
    dut._log.info("\nТест 5: Проверка EN=0 (Пауза)")
    
    await reset_dut(dut, enable=False) # Сброс с EN=0
    dut.en.value = 1 # Активируем EN
    
    # 1. Доходим до S5 (11011)
    seq_to_s5 = "11011"
    exp_to_s5 = "00000"
    await execute_sequence(dut, seq_to_s5, exp_to_s5) # State should be S5
    
    dut.en.value = 0 # Блокируем FSM
    
    # 2. Подаем разные входы при EN=0
    
    # Вход: 0 (должно остаться S5, т.к. EN=0)
    await Timer(CLK_PERIOD // 2, units='ns')
    dut["in"].value = 0
    await RisingEdge(dut.clk)
    await NextTimeStep()
    assert dut.detector_out.value == 0, "EN=0 Failed: Output changed"
    dut._log.info(f"Пауза 1 (In=0): Состояние сохранено.")

    # Вход: 1 (должно остаться S5, т.к. EN=0)
    await Timer(CLK_PERIOD // 2, units='ns')
    dut["in"].value = 1
    await RisingEdge(dut.clk)
    await NextTimeStep()
    assert dut.detector_out.value == 0, "EN=0 Failed: Output changed"
    dut._log.info(f"Пауза 2 (In=1): Состояние сохранено.")

    # 3. Активируем EN=1, и ожидаем переход в S6 (110110)
    dut.en.value = 1
    await Timer(CLK_PERIOD // 2, units='ns')
    dut["in"].value = 0 # Используем вход, который был подан последним
    await RisingEdge(dut.clk)
    await NextTimeStep()
    
    # S5 (in=0) -> S6. Output = 0
    assert dut.detector_out.value == 0, "EN=1 Failed: Output should be 0 (S6)"
    dut._log.info(f"Пауза 3: EN=1, перешли в S6.")

# ==============================================================================
# Pytest Runner 
# ==============================================================================

def test_detector_runner():
    """Pytest wrapper для запуска тестов детектора последовательности."""
    
    try:
        from cocotb_test.simulator import run
    except ImportError:
        raise ImportError("cocotb-test не найден. Установите: pip install cocotb-test")
    
    sim = os.getenv("SIM", "icarus")
    
    proj_path = Path(__file__).resolve().parent.parent
    
    # ПУТЬ К ВАШЕМУ MODULE.sv
    sources = [str(proj_path / "sources" / "detector.sv")]
    
    run(
        verilog_sources=sources,
        toplevel="detector",
        module="test_detector_hidden", 
        simulator=sim,
        sim_build=str(proj_path / "sim_build"),
        work_dir=str(proj_path / "tests"),
        timescale="1ns/1ps",
        compile_args=["-g2012"] if sim == "icarus" else [], 
        waves=True
    )

if __name__ == "__main__":
    test_detector_runner()