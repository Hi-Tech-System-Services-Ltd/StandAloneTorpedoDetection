import subprocess 
import time
import sys

def run_script():
    script_path = "E:\\flir\\Detection\\Cam1_2DetectionApp\\app\\cam2.py"

    while True:

        process = subprocess.Popen(["python", script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        try:
            for line in process.stdout:
                print(line.decode().strip())
            for line in process.stderr:
                print(line.decode().strip(), file=sys.stderr)

            process.wait()

            if process.returncode != 0:
                print()
        except KeyboardInterrupt:
            break

        finally:
            process.terminate()
            process.wait()

        time.sleep(1)



if __name__ == "__main__":
    run_script()
