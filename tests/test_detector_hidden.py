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

async def reset_dut(dut):
    """Сброс DUT (Device Under Test) и ожидание стабильности."""
    # Убедимся, что все порты доступны через синтаксис ['in']
    dut["in"].value = 0
    dut.rst.value = 1
    
    clk_period = CLK_PERIOD
    await Timer(clk_period, units="ns")
    await RisingEdge(dut.clk)
    
    dut.rst.value = 0
    await RisingEdge(dut.clk)
    
    assert dut.detector_out.value == 0, "Reset failed: detector_out should be 0"
    dut._log.info(f"DUT initialized and rst deasserted. State: S0.")

async def execute_sequence(dut, sequence: str, expected_outputs: str):
    """
    Подаёт последовательность входных данных (in) и проверяет выход (detector_out).
    Использует NextTimeStep для надежной проверки выхода Moore FSM.
    """
    assert len(sequence) == len(expected_outputs), "Sequence and expected output lengths must match."
    
    for i, (input_bit, expected_out) in enumerate(zip(sequence, expected_outputs)):
        input_val = int(input_bit)
        expected_val = int(expected_out)
        
        # 1. Устанавливаем входной бит
        dut["in"].value = input_val
        
        # Ждем стабилизации входа перед фронтом CLK (в середине периода)
        await Timer(CLK_PERIOD // 2, units='ns')
        
        # 2. Ждем положительный фронт CLK: current_state обновляется
        await RisingEdge(dut.clk)
        
        # 3. ЦИКЛ ДЕЛЬТЫ: Ждем, пока комбинационная логика обновит detector_out
        await NextTimeStep() 
        
        # 4. Чтение и проверка выхода
        current_out = int(dut.detector_out.value)
        
        dut._log.info(
            f"Step {i+1} (In={input_val}): Expected Out={expected_val}, Actual Out={current_out}"
        )
        
        # Проверка
        assert current_out == expected_val, \
            f"Mismatch at step {i+1}: Input='{sequence[:i+1]}'. Expected Out={expected_val}, Actual Out={current_out}"

# ==============================================================================
# Tests
# ==============================================================================

@cocotb.test()
async def test_sequence_detector_1101101(dut):
    """Проверка основных сценариев для детектора последовательности 1101101."""
    
    # Запускаем тактовый сигнал
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD, units="ns").start())
    
    dut._log.info("--- Начинаем проверку FSM 1101101 ---")

    # --- Сценарий 1: Успешное обнаружение 1101101 ---
    # FSM имеет 7 состояний, 7 входных битов.
    # Sequence: 1   1   0   1   1   0   1
    # State:    S1  S2  S3  S4  S5  S6  S7 (Detection)
    # Output:   0   0   0   0   0   0   1 
    seq_full = "1101101"
    exp_full = "0000001"
    
    dut._log.info(f"Тест 1: Полная последовательность: {seq_full}")
    await reset_dut(dut)
    await execute_sequence(dut, seq_full, exp_full)

    # --- Сценарий 2: Перекрывающиеся последовательности (1101101 + 10) ---
    # Текущее состояние после S7(1) -> S2 (т.к. 1101101 + 1 -> S2(11))
    # Sequence: 1   1   0   1   1   0   1   1   0
    # Output:   0   0   0   0   0   0   1   0   0
    seq_overlap = "110110110"
    exp_overlap = "000000100" 
    
    dut._log.info(f"Тест 2: Перекрытие (110110110)")
    await reset_dut(dut)
    await execute_sequence(dut, seq_overlap, exp_overlap)

    # --- Сценарий 3: Ложный старт (10 -> Сброс) ---
    # Sequence: 1   0   1   1   0   1
    # State:    S1  S0  S1  S2  S3  S4
    # Output:   0   0   0   0   0   0
    seq_false = "101101"
    exp_false = "000000"
    
    dut._log.info(f"Тест 3: Ложный старт (10...)")
    await reset_dut(dut)
    await execute_sequence(dut, seq_false, exp_false)


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