import unittest
import nbformat
import papermill as pm
import os
import re

def sanitize_and_sort_output(text):
    if not text:
        return ""

    lines = []
    raw_lines = text.strip().split('\n')

    for line in raw_lines:
        cleaned = line.strip()
        if not cleaned:
            continue

        # drop fragments (safety net for split text streams)
        if len(cleaned) <= 2 and re.match(r'^[()\d\s!]+$', cleaned):
            continue

        # handle histograms
        if "bin[" in cleaned:
            # standardize variable array values to 'x', keeping the bin index intact
            cleaned = re.sub(r'=\s*\d+', '= x', cleaned)
            lines.append(cleaned)
            continue

        # handle data race counters
        elif "counter =" in cleaned:
            cleaned = re.sub(r'counter\s*=\s*\d+', 'counter = x', cleaned)
            cleaned = re.sub(r'lost\s*\d+', 'lost x', cleaned)

            # parse milliseconds first, then seconds (order matters)
            cleaned = re.sub(r'\d+(\.\d+)?\s*ms\b', 'x.x ms', cleaned)
            cleaned = re.sub(r'\d+(\.\d+)?\s*s\b', 'x.x s', cleaned)
            lines.append(cleaned)
            continue

        # handle parallel core prints
        elif "Hello World!" in cleaned:
            count = cleaned.count("Hello World!")
            for _ in range(count):
                lines.append("Hello World! (x)")
            continue

        elif "Goodbye World!" in cleaned:
            count = cleaned.count("Goodbye World!")
            for _ in range(count):
                lines.append("Goodbye World! (x)")
            continue

        elif "This is another message!" in cleaned:
            lines.append("This is another message! (x)")
            continue

        # general timings, benchmarks, speedups & tables
        else:
            # parse dynamic speedups like "18.9x" or "6.4x" into "x.xx"
            cleaned = re.sub(r'\d+(\.\d+)?x', 'x.xx', cleaned)
            
            # parse floats/integers attached to execution seconds (e.g., "0.1241 s", "2 s")
            cleaned = re.sub(r'\d+(\.\d+)?\s*ms\b', 'x.x ms', cleaned)
            cleaned = re.sub(r'\d+(\.\d+)?\s*s\b', 'x.x s', cleaned)
            
            # parse metrics like "Total = 10000000" into standard values if they differ
            cleaned = re.sub(r'total\s*=\s*\d+', 'total = x', cleaned, flags=re.IGNORECASE)
            
            # general float / timing cleanup fallback
            cleaned = re.sub(r'\d+\.\d+(e\+\d+)?|\d+e\+\d+', 'x.x', cleaned)
            
            # if the line was a table header separator line (e.g., "------------"), 
            # compress it to prevent spaces from altering the alphabetical sort order
            if re.match(r"^[-'\s]+$", cleaned):
                cleaned = "---"
                
            lines.append(cleaned)

    # sort everything alphabetically to neutralize thread execution randomness
    lines.sort()
    return '\n'.join(lines)


class BaseNotebookTests(unittest.TestCase):
    __test__ = False
    kernel_name = None
    notebook_dir = None
    # flag to control sorting behavior dynamically
    should_sort_parallel_outputs = False
    skip_gpu_hardware_cells = False

    def test_notebooks(self):
        notebook_files = [
            f for f in os.listdir(self.notebook_dir)
            if f.endswith('.ipynb')
        ]

        if not notebook_files:
            self.fail(f"No notebooks found in {self.notebook_dir}")

        os.makedirs('executed', exist_ok=True)

        for name in notebook_files:
            # skip intentional error notebook if encountered in the target directories
            if name == "03_redefinition.ipynb":
                print(f"--> Skipping intentional error notebook: {name}")
                continue

            inp = os.path.join(self.notebook_dir, name)
            out = os.path.join('executed', name)

            with open(inp) as f:
                input_nb = nbformat.read(f, as_version=4)

            try:
                executed_notebook = pm.execute_notebook(
                    inp,
                    out,
                    log_output=True,
                    kernel_name=self.kernel_name,
                    cwd=os.path.dirname(os.path.abspath(inp))
                )
                if executed_notebook is None:
                    self.fail(f"Execution of notebook {name} returned None")
            except Exception as e:
                self.fail(f"Notebook {name} failed to execute: {e}")

            with open(out) as f:
                output_nb = nbformat.read(f, as_version=4)

            for i, (input_cell, output_cell) in enumerate(
                zip(input_nb.cells, output_nb.cells)
            ):
                if input_cell.cell_type == 'code' and output_cell.cell_type == 'code':
                    if bool(input_cell.outputs) != bool(output_cell.outputs):
                        self.fail(
                            f"Cell {i} in notebook {name} has mismatched output presence.\n"
                            f"Expected outputs: {bool(input_cell.outputs)}, "
                            f"Got: {bool(output_cell.outputs)}"
                        )
                    
                    elif input_cell.outputs:
                        # extract the raw text from reference cells
                        expected_raw = ''.join(
                            o.get('text', '') for o in input_cell.outputs if o.get('output_type') == 'stream'
                        )
                        # extract the raw text from execution cells
                        got_raw = ''.join(
                            o.get('text', '') for o in output_cell.outputs if o.get('output_type') == 'stream'
                        )
                        
                        # apply pointer memory hex sanitization to all types of notebooks
                        expected_raw = re.sub(r'0x[0-9a-fA-F]+', '0x7fffffff', expected_raw)
                        got_raw = re.sub(r'0x[0-9a-fA-F]+', '0x7fffffff', got_raw)
                        
                        # apply undefined behavior garbage integer sanitization to all types of notebooks
                        ub_pattern = r'(Undefined Behavior \(Reading freed heap\):\s*)-?\d+'
                        expected_raw = re.sub(ub_pattern, r'\1[garbage_int]', expected_raw)
                        got_raw = re.sub(ub_pattern, r'\1[garbage_int]', got_raw)

                        # conditional logic split here
                        if self.should_sort_parallel_outputs:
                            # run the heavy shuffling filters for parallel runs (openmp / cuda)
                            expected_clean = sanitize_and_sort_output(expected_raw)
                            got_clean = sanitize_and_sort_output(got_raw)
                        else:
                            # keep standard sequential text formats intact for core c++ notebooks
                            expected_clean = expected_raw.strip()
                            got_clean = got_raw.strip()
                        if self.skip_gpu_hardware_cells:
                            gpu_hardware_patterns = ["GPU:", "Streaming Multiprocessors", "Max threads per SM", "Max warps per SM"]
                            if any(p in expected_clean for p in gpu_hardware_patterns):
                                print(f"Skipping GPU hardware info cell {i} in {name}")
                                continue
                        
                        if expected_clean != got_clean:
                            self.fail(
                                f"Cell {i} in notebook {name} has mismatched output.\n\n"
                                f"--- Expected ---\n{expected_clean}\n\n"
                                f"--- Got ---\n{got_clean}"
                            )


class CppNotebookTests(BaseNotebookTests):
    __test__ = True
    kernel_name = 'xcpp23'  # standard core c++ kernel
    notebook_dir = 'xeus-cpp'
    should_sort_parallel_outputs = False  # stays sequential


class OpenMPNotebookTests(BaseNotebookTests):
    __test__ = True
    kernel_name = 'xcpp23-omp'
    notebook_dir = 'openmp'
    should_sort_parallel_outputs = True   # uses parallel filters


class CudaNotebookTests(BaseNotebookTests):
    __test__ = True
    kernel_name = 'xcpp23-cuda'
    notebook_dir = 'cuda'
    should_sort_parallel_outputs = True   # uses parallel filters
    skip_gpu_hardware_cells = True


if __name__ == '__main__':
    unittest.main()
