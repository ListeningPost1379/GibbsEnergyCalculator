import sys
import time
import argparse

# 这是一个伪造的计算程序，用于欺骗 JobManager
# 它会生成 Parser 能识别的最小化输出

def write_gaussian_out(filepath):
    with open(filepath, 'w') as f:
        f.write("Entering Gaussian System\n")
        f.write(" Charge = 0 Multiplicity = 1\n")
        f.write(" Standard orientation:\n")
        f.write(" ---------------------------------------------------------------------\n")
        f.write("    1          6             0.000000    0.000000    0.000000\n")
        f.write("    2          1             0.000000    0.000000    1.000000\n")
        f.write(" ---------------------------------------------------------------------\n")
        f.write(" SCF Done:  E(RB3LYP) = -100.000000000 A.U.\n")
        f.write(" Harmonic frequencies (cm**-1), ...\n")
        f.write(" Frequencies --   100.0000   200.0000   300.0000\n")
        f.write(" Zero-point correction=                           0.100000 (Hartree/Particle)\n")
        f.write(" Thermal correction to Gibbs Free Energy=         0.080000\n")
        f.write(" Stationary point found.\n")
        f.write(" Normal termination of Gaussian 16.\n")

def write_orca_out(filepath):
    with open(filepath, 'w') as f:
        f.write("* O   R   C   A *\n")
        f.write("Total Charge      Charge ....    0\n")
        f.write("Mult              Mult   ....    1\n")
        f.write("THE OPTIMIZATION HAS CONVERGED\n")
        f.write("VIBRATIONAL FREQUENCIES\n")
        f.write("   0:     100.00 cm**-1\n")
        f.write("FINAL SINGLE POINT ENERGY      -100.000000000000\n")
        f.write("G-E(el)           0.08000000 Eh\n")
        f.write("CARTESIAN COORDINATES (ANGSTROEM)\n")
        f.write("---------------------------------\n")
        f.write("C      0.000000    0.000000    0.000000\n")
        f.write("H      0.000000    0.000000    1.000000\n")
        f.write("---------------------------------\n")
        f.write("ORCA TERMINATED NORMALLY\n")

if __name__ == "__main__":
    # 使用方法: python mock_program.py {input_file} {output_file} {sleep_time}
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    duration = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0

    print(f"Mocking calculation for {input_file}...")
    time.sleep(duration) # 模拟耗时

    if input_file.endswith(".gjf"):
        write_gaussian_out(output_file)
    elif input_file.endswith(".inp"):
        write_orca_out(output_file)
    else:
        with open(output_file, 'w') as f:
            f.write("Unknown file type mock result.")