import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, NextTimeStep
from typing import List, Tuple
import os
from pathlib import Path

# ==============================================================================
# Конфигурация
# ==============================================================================
CLK_PERIOD = 10 

# ==============================================================================
# Helper Functions
# ==============================================================================

async def reset_dut(dut, enable=True):
    """Стандартная процедура инициализации."""
    dut["in"].value = 0
    dut.rst.value = 1
    dut.en.value = 1 if enable else 0
    await Timer(CLK_PERIOD, units="ns")
    await RisingEdge(dut.clk)
    dut.rst.value = 0
    await RisingEdge(dut.clk)
    await NextTimeStep()
    dut._log.info("DUT Reset Complete.")

async def execute_sequence(dut, sequence: str, expected_outputs: str):
    """Подача векторов и проверка выхода на каждом такте."""
    assert len(sequence) == len(expected_outputs), "Длины строк не совпадают"
    for i, (input_bit, expected_out) in enumerate(zip(sequence, expected_outputs)):
        dut["in"].value = int(input_bit)
        await RisingEdge(dut.clk)
        await NextTimeStep()
        actual_out = int(dut.detector_out.value)
        expected_val = int(expected_out)
        dut._log.info(f"Шаг {i+1:02d}: In={input_bit} | Exp={expected_val} | Act={actual_out}")
        assert actual_out == expected_val, f"Ошибка на шаге {i+1}!"

# ==============================================================================
# Тестовые сценарии
# ==============================================================================

@cocotb.test()
async def test_sequence_detector_comprehensive(dut):
    """Комплексный тест детектора с новой сложной последовательностью."""
    
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD, units="ns").start())

    # --- ТЕСТ 1: Базовая последовательность ---
    dut._log.info("\n>>> ТЕСТ 1: Базовая последовательность 1101101")
    await reset_dut(dut)
    await execute_sequence(dut, "1101101", "0000001")

    # --- ТЕСТ 2: Тройное перекрытие ---
    dut._log.info("\n>>> ТЕСТ 2: Перекрытия (7, 10, 13 такты)")
    await reset_dut(dut)
    await execute_sequence(dut, "1101101101101", "0000001001001")

    # --- ТЕСТ 3: Пауза EN на S5 ---
    dut._log.info("\n>>> ТЕСТ 3: Пауза EN=0 на состоянии S5")
    await reset_dut(dut)
    await execute_sequence(dut, "11011", "00000")
    dut.en.value = 0
    for _ in range(3):
        dut["in"].value = 1
        await RisingEdge(dut.clk); await NextTimeStep()
    dut.en.value = 1
    await execute_sequence(dut, "01", "01")

    # --- ТЕСТ 4: Проверка асинхронного сброса ---
    dut._log.info("\n>>> ТЕСТ 4: Асинхронный сброс")
    await reset_dut(dut)
    await execute_sequence(dut, "1101101", "0000001")
    await Timer(CLK_PERIOD / 2, units="ns")
    dut.rst.value = 1
    await NextTimeStep()
    assert int(dut.detector_out.value) == 0, "Выход не обнулился асинхронно!"
    dut.rst.value = 0

    # --- ТЕСТ 5: Длинная сложная последовательность (Ваш запрос) ---
    # Вход: 1 1 0 1 0 1 1 0 1 1 0 1 0 1 1 0 1 1 0 1 1 0 1
    # Анализ совпадений 1101101:
    # 1. 11010... (слом)
    # 2. 1101101 (завершается на 12-м бите)
    # 3. ...01101 (слом)
    # 4. 1101101 (завершается на 20-м бите)
    # 5. ...1101 (перекрытие, завершается на 23-м бите)
    
    seq_long = "11010110110101101101101"
    exp_long = "00000000000100000001001"
    
    dut._log.info(f"\n>>> ТЕСТ 5: Сложная последовательность\nIn:  {seq_long}\nExp: {exp_long}")
    await reset_dut(dut)
    await execute_sequence(dut, seq_long, exp_long)

    # --- ТЕСТ 6: Защита от 1111111 ---
    dut._log.info("\n>>> ТЕСТ 6: Серия единиц")
    await reset_dut(dut)
    await execute_sequence(dut, "11111111", "00000000")

    # --- ТЕСТ 7: EN=0 в момент детектирования ---
    dut._log.info("\n>>> ТЕСТ 7: EN=0 при финальном бите")
    await reset_dut(dut)
    await execute_sequence(dut, "110110", "000000")
    dut.en.value = 0
    dut["in"].value = 1
    await RisingEdge(dut.clk); await NextTimeStep()
    assert int(dut.detector_out.value) == 0
    dut.en.value = 1
    await execute_sequence(dut, "1", "1")

    dut._log.info("\n==============================================")
    dut._log.info("ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ УСПЕШНО")
    dut._log.info("==============================================")

# ==============================================================================
# Runner
# ==============================================================================

def test_detector_runner():
    try:
        from cocotb_test.simulator import run
    except ImportError:
        import pytest
        pytest.fail("pip install cocotb-test")
    
    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
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