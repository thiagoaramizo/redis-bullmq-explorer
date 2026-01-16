# BullMQ Explorer

Desktop GUI application to explore [BullMQ](https://docs.bullmq.io/) queues stored in Redis.

<img width="1427" height="838" alt="Captura de Tela 2026-01-15 às 14 22 24" src="https://github.com/user-attachments/assets/0073223f-a849-4852-adcd-442b2fd63841" />

You can:
- Connect to any reachable Redis instance.
- List all BullMQ queues by prefix.
- View jobs inside a queue with status, name, and data preview.
- Open a full job details modal and copy the job ID or data.
- Delete individual jobs from the selected queue.
- Filter by job status, search inside job data, and paginate results.
- See live Redis information (version, mode, memory, clients).
- Enable auto‑refresh every 5 seconds to keep data up‑to‑date.

<img width="1434" height="835" alt="Captura de Tela 2026-01-15 às 14 22 02" src="https://github.com/user-attachments/assets/9d051ebb-dd9f-4e2b-afda-a302d6e34198" />

The app has a modern dark UI and is fully in English.


---

## 1. Who is this for?

This project is designed so that **anyone**, even without strong programming experience, can:
- Download the code.
- Install the application.
- Run it on their own computer.

You only need:
- A basic terminal (command line) on your system.
- An installed Redis server (or access to one).

If you follow the steps below **exactly**, you should be able to run the app without needing to write any code.

---

## 2. Requirements

Before you start, make sure you have:

- **Operating System**
  - Windows 10 or later
  - macOS 12 or later
  - Any recent Linux distribution

- **Python**
  - Version **3.9 or newer**  
  - Check your version:
    ```bash
    python --version
    ```
    or
    ```bash
    python3 --version
    ```

- **Git**
  - Used to download (clone) the project.
  - Check if it is installed:
    ```bash
    git --version
    ```

- **Redis server**
  - You must have a running Redis instance.
  - If you do not have Redis, the simplest way for beginners is to use Docker:
    ```bash
    docker run --name redis -p 6379:6379 redis:7
    ```
  - Or install Redis natively using your system’s package manager or official installers.

---

## 3. Clone the project

Open your terminal (Command Prompt / PowerShell on Windows, Terminal on macOS/Linux) and run:

```bash
git clone https://github.com/thiagoaramizo/redis-bullmq-explorer.git
cd redis-bullmq-explorer
```

This downloads the project code into a new folder called `redis-bullmq-explorer` and moves you into that folder.

---

## 4. Create a virtual environment (recommended)

A **virtual environment** is an isolated Python environment that keeps this project’s dependencies separate from the rest of your system.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

You should now see `(.venv)` at the beginning of your terminal prompt, indicating the virtual environment is active.

### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If PowerShell blocks the script, you may need to allow script execution:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then run the `Activate.ps1` command again.

### Windows (Command Prompt)

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

After activation, your prompt should show `(.venv)` as well.

---

## 5. Install the project and dependencies

With the virtual environment active and inside the project folder, run:

```bash
pip install -e .
```

What this does:
- Installs required libraries: **redis** and **PySide6** (the GUI toolkit).
- Registers a command called `redis-bullmq-explorer` that starts the app.
- The `-e` flag (editable mode) makes development easier if you change the code.

If you prefer a normal installation (no development), you can run:

```bash
pip install .
```

> If you see errors saying “pip not found”, try `python -m pip install -e .` or `python3 -m pip install -e .`.

---

## 6. Starting the application

After installation, still inside the virtual environment, if you use it, in the project folder, run:

```bash
python run.py
```

This will open the BullMQ Explorer desktop window.

---

## 7. Connecting to Redis and BullMQ

When the app opens, you will see at the top:
- A text box labeled **Redis URL**
- A text box labeled **Prefix**
- A **Connect** button

### 7.1. Redis URL

This is the address of your Redis server. Some common examples:

- Local Redis on default port and database 0:
  ```text
  redis://localhost:6379/0
  ```
- Remote Redis with password:
  ```text
  redis://:your_password@your-redis-host:6379/0
  ```

The app comes with a default value:

```text
redis://localhost:6379/0
```

If you are running Redis locally with default settings, you can leave this as-is.

### 7.2. Prefix

BullMQ stores its data in Redis using a **prefix** (by default, `bull`).

- If your BullMQ queues use the default prefix, just use:
  ```text
  bull
  ```
- If your application uses a custom prefix, type that value instead.

### 7.3. Connect

1. Fill or confirm the **Redis URL**.
2. Fill or confirm the **Prefix**.
3. Click **Connect**.

The application will:
- Connect to Redis.
- Discover all BullMQ queues for that prefix.
- Show them in the left-hand **Queues** list.
- Show a thin info bar under the header with:
  - Redis version
  - Mode (standalone/cluster)
  - Used memory vs total memory
  - Number of connected clients

<img width="1434" height="835" alt="Captura de Tela 2026-01-15 às 14 22 02" src="https://github.com/user-attachments/assets/e89f687e-7aec-4d37-9154-58ef378d2a79" />

If the connection fails, you will see an error message dialog.

---

## 8. Exploring queues and jobs

### 8.1. Queue list (left side)

- The left panel shows a list of all discovered queues.
- Click on a queue name to select it.

After selecting a queue:
- The right side will show job statistics and the job table.

### 8.2. Status cards (top right)

Just above the jobs table, you will see horizontal **status cards**, for example:
- `WAIT`
- `ACTIVE`
- `DELAYED`
- `COMPLETED`
- `FAILED`

These cards:
- Show the **count** of jobs in each status.
- Can be clicked to filter the jobs table by that status.
- Clicking the selected card again will remove the filter.

### 8.3. Search and pagination

Below the status cards:
- A **Search in Data...** box lets you search:
  - By job ID
  - Inside the JSON data of each job
- Press Enter or click **Search** to apply it.

Below the jobs table:
- Pagination controls:
  - `<< Prev` and `Next >>`
  - Current page indicator (`Page X / Y`)
  - Total number of jobs

### 8.4. Auto-refresh and manual refresh

![Jobs table and auto-refresh](redis_bullmq_explorer/assets/Captura de Tela 2026-01-15 às 14.23.33.png)

On the right side of the status cards:
- A small checkbox: **Auto-refresh (5s)**
  - When enabled, the app refreshes the job list every 5 seconds without blocking the UI.
- A **Refresh** button
  - Forces an immediate manual refresh of the current queue’s job data and counters.

### 8.5. Job actions (View, Delete)

In the **Actions** column of the jobs table:

- **View**
  - Opens a modal dialog with full job details:
    - ID
    - Name
    - State
    - Full JSON data (pretty-printed when possible)
  - Includes buttons to quickly **copy**:
    - Job ID
    - Job data

- **Delete**
  - Asks for confirmation.
  - Removes the job from all relevant Redis keys (across states).
  - Refreshes the table when done.

---

## 9. Common problems and troubleshooting

### 9.1. The app does not start

- Make sure you installed the project inside the virtual environment:
  ```bash
  pip install -e .
  ```
- Try running with Python directly:
  ```bash
  python -m redis_bullmq_explorer.app
  ```
- If you see an error saying a module is missing (for example `redis` or `PySide6`):
  - Re-run:
    ```bash
    pip install -e .
    ```

### 9.2. Cannot connect to Redis

- Double-check the **Redis URL**.
- Verify that Redis is running:
  - If using Docker, run:
    ```bash
    docker ps
    ```
    and check that the Redis container is listed.
- If Redis is on another machine:
  - Make sure firewalls or security rules allow connections on port 6379 (or your custom port).

### 9.3. Queues are empty or missing

- Confirm the **Prefix** matches the one used by your BullMQ application.
- Ensure your BullMQ application is pointing to the same Redis instance (same host, port, database).

---

## 10. Development notes

If you want to modify the code:

1. Clone the repository and create a virtual environment (steps 3–4 above).
2. Install in editable mode:
   ```bash
   pip install -e .
   ```
3. Run the app directly from the source:
   ```bash
   python -m redis_bullmq_explorer.app
   ```
4. Edit files under the `redis_bullmq_explorer/` directory, for example:
   - [app.py](redis_bullmq_explorer/app.py) – application entrypoint wiring.
   - [presentation_qt.py](redis_bullmq_explorer/presentation_qt.py) – Qt GUI (main window and widgets).
   - [infrastructure_redis_bullmq.py](redis_bullmq_explorer/infrastructure_redis_bullmq.py) – Redis/BullMQ data access.
   - [application_explorer.py](redis_bullmq_explorer/application_explorer.py) – application services between UI and Redis.

---

## 11. License

This project is licensed under the **MIT License**.

You are free to use, modify, and distribute it, as long as you include the license text and attribution.
