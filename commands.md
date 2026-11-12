ANA REMEMBERS: COMMANDS
(all from C:\Users\Favour\ana-remembers unless noted)

START THE APP (two terminals)
  Terminal 1, backend:   python -m uvicorn api:app --reload --host 0.0.0.0
  Terminal 2, app:       cd mobile
                         npx.cmd expo start
  Laptop browser:        http://localhost:8081
  Phone (same Wi-Fi):    http://<laptop IP>:8081   (IP = "Metro" line in the Expo terminal)
  Reload app:            press r in the Expo terminal
  Stop anything:         Ctrl + C

BENCHMARKS (screenshots for evidence)
  python benchmark_semantic.py    free, embeddings only
  python benchmark_memory.py      memory options vs tokens
  python benchmark_models.py      free tier vs Fontys (uses ~10 budget calls)
  python benchmark_thinking.py    thinking default vs low (uses ~10 budget calls)

MONITORING
  Browser dashboard:     http://localhost:8000/monitoring?key=<ADMIN_KEY from .env>
  Power BI:              open the .pbix, press Refresh

ANA REMEMBERS: COMMANDS
(all from C:\Users\Favour\ana-remembers unless noted)

START THE APP (two terminals)
  Terminal 1, backend:   python -m uvicorn api:app --reload --host 0.0.0.0
  Terminal 2, app:       cd mobile
                         npx.cmd expo start
  Laptop browser:        http://localhost:8081
  Phone (same Wi-Fi):    http://<laptop IP>:8081   (IP = "Metro" line in the Expo terminal)
  Reload app:            press r in the Expo terminal
  Stop anything:         Ctrl + C

BENCHMARKS (screenshots for evidence)
  python benchmark_semantic.py    free, embeddings only
  python benchmark_memory.py      memory options vs tokens
  python benchmark_models.py      free tier vs Fontys (uses ~10 budget calls)
  python benchmark_thinking.py    thinking default vs low (uses ~10 budget calls)

MONITORING
  Browser dashboard:     http://localhost:8000/monitoring?key=<ADMIN_KEY from .env>
  Power BI:              open the .pbix, press Refresh

GIT (after changes)
  git add .
  git commit -m "what changed"
  git push

IF POWERSHELL BLOCKS npx
  use npx.cmd, or once:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned