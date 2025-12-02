`timescale 1ns / 1ps

module detector(
	input clk, // clock signal
	input rst, // reset input (active high)
	input en,  // <--- ДОБАВЛЕН НОВЫЙ ВХОД ENABLE
	input in, // binary input
	output reg detector_out // output of the sequence detector (Moore FSM)
);
	// 8 состояний (3 бита) для последовательности 1101101
	localparam S0 = 3'b000; // Ожидаем 1 / Начало (Nothing matched)
	localparam S1 = 3'b001; // 1
	localparam S2 = 3'b010; // 11
	localparam S3 = 3'b011; // 110
	localparam S4 = 3'b100; // 1101
	localparam S5 = 3'b101; // 11011
	localparam S6 = 3'b110; // 110110
	localparam S7 = 3'b111; // 1101101 (Финальное состояние / Обнаружено)

	reg [2:0] current_state, next_state; // current state and next state

// --- 1. Регистр состояния (Sequential Logic) ---
	always @(posedge clk, posedge rst) begin
		if(rst == 1) begin
			current_state <= S0; // Асинхронный сброс в S0
		end else if (en == 1) begin // <--- ДОБАВЛЕНО: Обновление только при EN=1
			current_state <= next_state; 
		end else begin
            // Если en=0, состояние сохраняется
			current_state <= current_state; // или current_state <= current_state;
		end
	end

// --- 2. Логика следующего состояния (Combinational Logic) ---
    // Эта логика остается неизменной, так как она вычисляет NEXT_STATE
    // вне зависимости от EN. Управление обновлением происходит в блоке 1.
	always @(current_state, in) begin
		next_state = S0; // Значение по умолчанию, если не определено
		
		case(current_state)
			S0: begin // Ожидаем 1
				if(in == 1) next_state = S1;
				else next_state = S0;
			end
			S1: begin // 1. Ожидаем 1
				if(in == 1) next_state = S2;
				else next_state = S0;
			end
			S2: begin // 11. Ожидаем 0
				if(in == 0) next_state = S3;
				else next_state = S2;
			end
			S3: begin // 110. Ожидаем 1
				if(in == 1) next_state = S4;
				else next_state = S0;
			end
			S4: begin // 1101. Ожидаем 1
				if(in == 1) next_state = S5;
				else next_state = S0;
			end
			S5: begin // 11011. Ожидаем 0
				if(in == 0) next_state = S6;
				else next_state = S2;
			end
			S6: begin // 110110. Ожидаем 1
				if(in == 1) next_state = S7;
				else next_state = S3;
			end
			S7: begin // 1101101 (Обнаружено).
				if(in == 1) next_state = S2;
				else next_state = S3;
			end
			default: next_state = S0;
		endcase
	end

// --- 3. Логика выхода (Output Logic - Moore) ---
	always @(current_state) begin
		case(current_state)
			S7: detector_out = 1;
			default: detector_out = 0;
		endcase
	end
endmodule