# FarmGuard

A Python + Streamlit crop observation and inspection prioritization project.

## Run locally

1. Install Python 3.10 or newer.
2. Open this folder in VS Code.
3. Open the VS Code terminal.
4. Create and activate a virtual environment (optional but recommended).
5. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

6. Run:

   ```bash
   streamlit run app.py
   ```

## Included features

- Dashboard with summary metrics and charts
- Crop observation recording
- Farm record search and sorting
- Crop observation history
- Transparent inspection priority score
- Inspection status management
- DSA demonstration page
- SQLite database

## DSA implementations

- Tree ADT: `dsa/tree.py`
- Max Heap: `dsa/max_heap.py`
- Linked List: `dsa/linked_list.py`
- Hash Table with separate chaining: `dsa/hash_table.py`
- Merge Sort: `dsa/sorting.py`

## Deployment to Streamlit Community Cloud

Upload the contents of this project folder to a GitHub repository. In Streamlit Community Cloud, choose that repository, select the correct branch, and set the main file path to `app.py`.

## Database note

The app creates `farmguard.db` locally. On hosted platforms with ephemeral local storage, SQLite data may not persist across restarts or redeployments. Use a hosted database for long-term multi-user production data.

## Scope and limitation

FarmGuard organizes farmer-entered observations and ranks records for inspection. It is not a crop disease diagnostic tool and does not prescribe treatments.
