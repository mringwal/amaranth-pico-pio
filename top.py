from asm.adafruit_pioasm import assemble
from amaranth import *
from amaranth.sim import Simulator
from amaranth.lib import stream, wiring
from amaranth.lib.wiring import In, Out
import os


INSTRUCTION_JMP  = 0
INSTRUCTION_WAIT = 1
INSTRUCTION_IN   = 2
INSTRUCTION_OUT  = 3
INSTRUCTION_PUSH = 4
INSTRUCTION_PULL = 5
INSTRUCTION_MOV  = 6
INSTRUCTION_SET  = 7

SET_DESTINATION_PINS = 0

class PIO_StateMachine(Elaboratable):

    # program counter and 'exec' register
    PC   = Signal(5)
    EXEC = Signal(16)

    # Input Shift Register
    ISR  = Signal(32)

    # Output Shift Register
    OSR  = Signal(32)

    # Scratch registers
    X    = Signal(32)
    Y    = Signal(32)

    # GPIO Outputs
    GPIO_Output_State    = Signal(32)
    GPIO_Output_Modified = Signal(32)

    GPIO_Direction_State    = Signal(32)
    GPIO_Direction_Modified = Signal(32)

    # instruction decoding
    Instruction = Signal(3)
    Delay_Sideset = Signal(5)
    Operand_4_0 = Signal(5)
    Operand_7_5 = Signal(3)

    def __init__(self, program):
        super().__init__()
        self.program = Array(program)


    def elaborate(self, platform) -> Module:
        m = Module()

        m.d.comb += [
            self.Instruction.eq(self.EXEC[13:16]),
            self.Delay_Sideset.eq(self.EXEC[8:13]),            
            self.Operand_4_0.eq(self.EXEC[0:5]),            
            self.Operand_7_5.eq(self.EXEC[5:8])            
        ]

        with m.FSM():
            with m.State("FETCH"):
                m.d.sync += [
                    Print("FETCH"),
                    self.EXEC.eq(self.program[self.PC]),
                ]
                m.next = "EXEC"

            with m.State("EXEC"):
                m.d.sync += [
                    Print("EXEC", self.Instruction),
                ]
                with m.If(self.Instruction == INSTRUCTION_SET):
                    with m.If(self.Operand_7_5 == SET_DESTINATION_PINS):
                        m.d.sync += [
                            Print("- Set PINS, value: ", self.Operand_4_0)
                        ]                        
                    with m.Else():
                        m.d.sync += [
                            Print("- Set Destination", self.Operand_7_5)
                        ]
                m.next = "NEXT"

            with m.State("NEXT"):
                # next instruction
                # TODO: support WRAP
                with m.If(self.PC == (len(self.program) - 1)):
                    m.d.sync += [
                        Print("PC:  0 - WRAP"),
                        self.PC.eq(0)
                    ]
                with m.Else():
                    m.d.sync += [
                        Print("PC: ", self.PC + 1),
                        self.PC.eq(self.PC + 1)
                    ]
                m.next = "FETCH"

        return m


async def stream_get(ctx, stream):
    ctx.set(stream.ready, 1)
    payload, = await ctx.tick().sample(stream.payload).until(stream.valid)
    ctx.set(stream.ready, 0)
    return payload


async def stream_peek(ctx, stream_payload, stream_ready, stream_valid):
    payload, = await ctx.tick().sample(stream_payload).until(stream_valid & stream_ready)
    return payload


async def testbench(ctx):
    for i in range(100):
         await ctx.tick()


# CLI
asm = 'asm/square.asm'

# Convert ASM into binary stream
with open(asm,"r") as f:
    text = f.read();
    f.close()

print(text)
program = assemble(text, True)

# PIO State Machine Config - terms from datasheet

# Each PIO has 4 state machines

# Base and count of SIDESET BITs. max 5
EXECCTRL_SIDE_EN = 0
EXECCTRL_SIDE_PINDIR = 0
PINCTRL_SIDESET_BASE = 0
PINCTRL_SIDESET_COUNT = 0

# Base and count of SET BITs. max 5
PINCTRL_SET_BASE = 0
PINCTRL_SET_COUNT = 0

# Base and count of OUT BITs
PINCTRL_OUT_BASE = 0
PINCTRL_OUT_COUNT = 0

# Base and count of IN BITs
PINCTRL_IN_BASE = 0
PINCTRL_IN_COUNT = 0

# Wrap: continue at WRAP_TARGET after WRAP
WRAP_TARGET = 0
WRAP = 32

# PIO frequency in HZ
FREQ = 1000


# Setup 
dut = PIO_StateMachine(program)

sim = Simulator(dut)
sim.add_clock(1e-6)
sim.add_testbench(testbench)

with sim.write_vcd("top.vcd"):
    sim.run()

# from amaranth_boards.tinyfpga_bx import TinyFPGABXPlatform
# from amaranth.build import Resource, Pins, Attrs
# 
# # Connect pins
# platform = TinyFPGABXPlatform()
# platform.add_resources([])
# platform.build(dut, do_program=False)
