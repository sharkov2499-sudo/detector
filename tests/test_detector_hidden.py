import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, NextTimeStep
from typing import List, Tuple
import os
from pathlib import Path

# Период тактового сигнала
CLK_PERIOD = 10 

# ==============================================================================
# Вспомогательные функции (Helper Functions)
# ==============================================================================

async def reset_dut(dut, enable=True):
    """Сброс DUT и ожидание стабильности, установка EN."""
    dut["in"].value = 0
    dut.rst.value = 1
    
    # Установка EN в 1, если не требуется иное
    if enable:
        dut.en.value = 1
    else:
        dut.en.value = 0
    
    await Timer(CLK_PERIOD, units="ns")
    await RisingEdge(dut.clk)
    
    dut.rst.value = 0
    await RisingEdge(dut.clk)
    
    assert dut.detector_out.value == 0, "Reset failed: detector_out should be 0"
    dut._log.info(f"DUT initialized and rst deasserted. EN={dut.en.value}")

async def execute_sequence(dut, sequence: str, expected_outputs: str):
    """
    Подаёт последовательность входных данных (in) и проверяет выход (detector_out).
    Для данного модуля выход появляется на том же такте (Mealy-поведение).
    """
    assert len(sequence) == len(expected_outputs), "Sequence and expected output lengths must match."
    
    for i, (input_bit, expected_out) in enumerate(zip(sequence, expected_outputs)):
        input_val = int(input_bit)
        expected_val = int(expected_out)
        
        # 1. Устанавливаем входное значение
        dut["in"].value = input_val
        
        # 2. Ждем фронта синхросигнала
        await RisingEdge(dut.clk)
        
        # 3. Ждем микротакт для обновления сигналов в симуляторе
        await NextTimeStep() 
        
        current_out = int(dut.detector_out.value)
        
        dut._log.info(
            f"Step {i+1} (In={input_val}): Expected Out={expected_val}, Actual Out={current_out}"
        )
        
        # Проверка соответствия
        assert current_out == expected_val, \
            f"Mismatch at step {i+1}: Input='{sequence[:i+1]}'. Expected Out={expected_val}, Actual Out={current_out}"

# ==============================================================================
# Тесты (Tests)
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

    # --- Сценарий 2: Перекрывающиеся последовательности (7, 10, 13 такты) ---
    # При входе 1101101101101 совпадения на 7, 10 и 13 позициях
    seq_overlap = "1101101101101" 
    exp_overlap = "0000001001001" 
    
    dut._log.info(f"\nТест 2: Тройное перекрытие")
    await reset_dut(dut)
    await execute_sequence(dut, seq_overlap, exp_overlap)

    # --- Сценарий 3: Ложный старт (10 -> Сброс) ---
    seq_false = "10110100"
    exp_false = "00000000"
    
    dut._log.info(f"\nТест 3: Ложный старт (10 -> Сброс)")
    await reset_dut(dut)
    await execute_sequence(dut, seq_false, exp_false)
    
    # --- Сценарий 4: Максимальный сброс (11010) ---
    seq_max_reset = "11010"
    exp_max_reset = "00000"
    
    dut._log.info(f"\nТест 4: Максимальный сброс (11010)")
    await reset_dut(dut)
    await execute_sequence(dut, seq_max_reset, exp_max_reset)

    # --- Сценарий 5: Проверка EN=0 (Пауза) ---
    dut._log.info("\nТест 5: Проверка EN=0 (Пауза)")
    
    await reset_dut(dut, enable=False) 
    dut.en.value = 1 
    
    # 1. Доходим до S5 (11011)
    await execute_sequence(dut, "11011", "00000") 
    
    # 2. Блокируем автомат
    dut.en.value = 0 
    
    # Подаем входы, которые должны быть проигнорированы
    for _ in range(3):
        dut["in"].value = 0 # Без EN=1 состояние S5 не должно перейти в S6
        await RisingEdge(dut.clk)
        await NextTimeStep()
        assert int(dut.detector_out.value) == 0, "Ошибка: выход изменился при EN=0"
    
    dut._log.info(f"Пауза: Состояние S5 сохранено при EN=0.")

    # 3. Активируем EN=1 и дозавершаем последовательность (0 -> 1)
    dut.en.value = 1
    # Последовательность: S5 --(0)--> S6 --(1)--> S7 (Выход 1)
    await execute_sequence(dut, "01", "01")
    dut._log.info("Тест 5 пройден успешно.")

# ==============================================================================
# Pytest Runner 
# ==============================================================================

def test_detector_runner():
    """Pytest wrapper для запуска тестов детектора последовательности."""
    
    try:
        from cocotb_test.simulator import run
    except ImportError:
        import pytest
        pytest.fail("cocotb-test не найден. Установите: pip install cocotb-test")
    
    sim = os.getenv("SIM", "icarus")
    
    # Определение путей
    proj_path = Path(__file__).resolve().parent.parent
    sources = [str(proj_path / "sources" / "detector.sv")]
    
    # Проверка наличия файла исходников
    if not Path(sources[0]).exists():
        import pytest
        pytest.fail(f"Файл исходного кода не найден: {sources[0]}")
    
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