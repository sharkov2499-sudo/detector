module detector(
	input clk,
	input rst,
	input en,
	input in,
	output reg detector_out
);

	localparam S0 = 3'b000; // (Nothing matched)
	localparam S1 = 3'b001; // 1
	localparam S2 = 3'b010; // 11
	localparam S3 = 3'b011; // 110
	localparam S4 = 3'b100; // 1101
	localparam S5 = 3'b101; // 11011
	localparam S6 = 3'b110; // 110110
	localparam S7 = 3'b111; // 1101101 (final state)

	reg [2:0] current_state, next_state;


	always @(posedge clk, posedge rst) begin
		if(rst == 1) begin
			current_state <= S0;
		end else if (en == 1) begin
			current_state <= next_state;
		end else begin
			current_state <= current_state;
		end
	end

	always @(current_state, in) begin
		next_state = S0;
		
		case(current_state)
			S0: begin
				if(in == 1) next_state = S1;
				else next_state = S0;
			end
			S1: begin
				if(in == 1) next_state = S2;
				else next_state = S0;
			end
			S2: begin
				if(in == 0) next_state = S3;
				else next_state = S2;
			end
			S3: begin
				if(in == 1) next_state = S4;
				else next_state = S0;
			end
			S4: begin
				if(in == 1) next_state = S5;
				else next_state = S0;
			end
			S5: begin
				if(in == 0) next_state = S6;
				else next_state = S2;
			end
			S6: begin
				if(in == 1) next_state = S7;
				else next_state = S3;
			end
			S7: begin
				if(in == 1) next_state = S2;
				else next_state = S3;
			end
			default: next_state = S0;
		endcase
	end

	always @(current_state) begin
		case(current_state)
			S7: detector_out = 1;
			default: detector_out = 0;
		endcase
	end
endmodule