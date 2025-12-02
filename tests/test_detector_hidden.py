import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, NextTimeStep # <-- ИМПОРТИРУЕМ NextTimeStep
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
    dut["in"].value = 0
    dut.rst.value = 1
    
    clk_period = CLK_PERIOD
    # Удерживаем сброс
    await Timer(clk_period, units="ns")
    await RisingEdge(dut.clk)
    
    dut.rst.value = 0
    # Ждем один такт для дезактивации сброса
    await RisingEdge(dut.clk)
    
    # Проверяем, что выход сброшен
    assert dut.detector_out.value == 0, "Reset failed: detector_out should be 0"
    
    dut._log.info(f"DUT initialized and rst deasserted. State: {int(dut.current_state.value)}.")

async def execute_sequence(dut, sequence: str, expected_outputs: str):
    """
    Подаёт последовательность входных данных (in) и проверяет выход (detector_out).
    Использует NextTimeStep для надежной проверки выхода Moore FSM.
    """
    assert len(sequence) == len(expected_outputs), "Sequence and expected output lengths must match."
    
    for i, (input_bit, expected_out) in enumerate(zip(sequence, expected_outputs)):
        # Парсинг значений
        input_val = int(input_bit)
        expected_val = int(expected_out)
        
        # 1. Устанавливаем входной бит
        dut["in"].value = input_val
        
        # Ждем стабилизации входа перед фронтом CLK (в середине периода)
        await Timer(CLK_PERIOD // 2, units='ns')
        
        # 2. Ждем положительный фронт CLK: current_state обновляется
        await RisingEdge(dut.clk)
        
        # 3. ДОПОЛНИТЕЛЬНЫЙ ЦИКЛ ДЕЛЬТЫ (NextTimeStep): 
        # Ждем, пока комбинационная логика (detector_out) обновится.
        await NextTimeStep() # <--- ИСПРАВЛЕНИЕ: Используем NextTimeStep вместо Timer(0)
        
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
async def test_sequence_detector_1011(dut):
    """Проверка основных сценариев для детектора последовательности 1011."""
    
    # Запускаем тактовый сигнал
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD, units="ns").start())
    
    dut._log.info("--- Начинаем проверку FSM 1011 ---")

    # --- Сценарий 1: Успешное обнаружение 1011 ---
    seq_1011 = "1011"
    exp_1011 = "0001"
    
    dut._log.info(f"Тест последовательности: {seq_1011}")
    await reset_dut(dut)
    await execute_sequence(dut, seq_1011, exp_1011)

    # --- Сценарий 2: Перекрывающиеся последовательности (10111) ---
    seq_overlap = "10111"
    exp_overlap = "00010" 
    
    dut._log.info(f"Тест перекрывающейся последовательности: {seq_overlap}")
    await reset_dut(dut)
    await execute_sequence(dut, seq_overlap, exp_overlap)

    # --- Сценарий 3: Ложный старт (111011) ---
    seq_false = "111011"
    exp_false = "000001"
    
    dut._log.info(f"Тест ложного старта: {seq_false}")
    await reset_dut(dut)
    await execute_sequence(dut, seq_false, exp_false)


# ==============================================================================
# Pytest Runner 
# ==============================================================================

def test_detector_runner():
    """Pytest wrapper для запуска тестов детектора последовательности."""
    
    # Импортируем run из cocotb_test.simulator
    try:
        from cocotb_test.simulator import run
    except ImportError:
        raise ImportError("cocotb-test не найден. Установите: pip install cocotb-test")
    
    sim = os.getenv("SIM", "icarus")
    
    # Определяем путь к корню проекта (на два уровня выше этого файла)
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