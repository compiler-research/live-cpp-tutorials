import unittest
import nbformat
import papermill as pm
import os
import re

class NotebookTests(unittest.TestCase):
    kernel_name = 'xcpp23'  # Your standard C++ kernel name
    notebook_dir = 'xeus-cpp'

    def test_notebooks(self):
        # Scan the target folder for notebooks
        notebook_files = [
            f for f in os.listdir(self.notebook_dir)
            if f.endswith('.ipynb')
        ]

        if not notebook_files:
            self.fail(f"No notebooks found in directory: {self.notebook_dir}")

        os.makedirs('executed', exist_ok=True)

        for name in notebook_files:
        
            if name == "03_redefinition.ipynb":
                print(f"--> Skipping intentional error notebook: {name}")
                continue
        
            inp = os.path.join(self.notebook_dir, name)
            out = os.path.join('executed', name)

            # Load the reference notebook (Expected)
            with open(inp) as f:
                input_nb = nbformat.read(f, as_version=4)

            # Run the notebook via Papermill
            try:
                executed_notebook = pm.execute_notebook(
                    inp,
                    out,
                    log_output=True,
                    kernel_name=self.kernel_name
                )
                if executed_notebook is None:
                    self.fail(f"Execution of notebook {name} returned None")
            except Exception as e:
                self.fail(f"Notebook {name} failed to execute smoothly: {e}")

            # Load the freshly executed notebook (Got)
            with open(out) as f:
                output_nb = nbformat.read(f, as_version=4)

            # Compare cell outputs exactly
            for i, (input_cell, output_cell) in enumerate(
                zip(input_nb.cells, output_nb.cells)
            ):
                if input_cell.cell_type == 'code' and output_cell.cell_type == 'code':
                    # Extract and clean exact raw text streams
                    expected_text = ''.join(
                        o.get('text', '') for o in input_cell.outputs if o.get('output_type') == 'stream'
                    ).strip()
                    
                    got_text = ''.join(
                        o.get('text', '') for o in output_cell.outputs if o.get('output_type') == 'stream'
                    ).strip()

                    expected_text = re.sub(r'0x[0-9a-fA-F]+', '0x7fffffff', expected_text)
                    got_text = re.sub(r'0x[0-9a-fA-F]+', '0x7fffffff', got_text)
                    
                    ub_pattern = r'(Undefined Behavior \(Reading freed heap\):\s*)-?\d+'
                    expected_text = re.sub(ub_pattern, r'\1[GARBAGE_INT]', expected_text)
                    got_text = re.sub(ub_pattern, r'\1[GARBAGE_INT]', got_text)

                    if expected_text != got_text:
                        self.fail(
                            f"Cell {i} in notebook '{name}' has mismatched output.\n\n"
                            f"--- Expected ---\n{expected_text}\n\n"
                            f"--- Got ---\n{got_text}"
                        )

if __name__ == '__main__':
    unittest.main()
