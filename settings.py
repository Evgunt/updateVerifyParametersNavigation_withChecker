# ============================================================
# SETTINGS
# ============================================================
import os

SINGBOX_PATH = "./singBox/sing-box.exe"
SINGBOX_CONFIG = "sing_box_config.json"

LOCAL_PORT_START = 10800

OUTPUT_FILENAME = "fast_vless.txt"
CHECKPOINT_FILENAME = ".fast_vless_checkpoint.json"

BATCH_SIZE = 300

# Начальная / минимальная / максимальная конкуррентность.
INITIAL_CONCURRENT_TESTS = 100
MIN_CONCURRENT_TESTS = 50
MAX_CONCURRENT_TESTS = 200
# GLOBAL STATE
current_concurrency = INITIAL_CONCURRENT_TESTS

PROXY_TIMEOUT = 6.0
BATCH_TIMEOUT = 40.0

HTTP_CONNECT_TIMEOUT = 2.5
HTTP_READ_TIMEOUT = 2.5
HTTP_WRITE_TIMEOUT = 2.5
HTTP_POOL_TIMEOUT = 1.0

SINGBOX_START_DELAY = 1.5
CLEANUP_DELAY = 0.5

RETRY_COUNT = 0

TARGET_WORKING = 60

TEST_URLS = "https://www.google.com/generate_204"

IP_CHECK_URL = "https://api.ipify.org?format=json"

GIT_BRANCH = "main"

COMMIT_MESSAGE = (
    "Auto-update: 60 fast configs via Sing-box"
)

REPO_PATH = os.path.dirname(
    os.path.abspath(__file__)
)
# Путь к файлу со ссылками
SOURCES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources.txt")

# Автоматически читаем ссылки из файла, если он существует
if os.path.exists(SOURCES_FILE):
    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        # Читаем строки, убираем пробелы/переносы и отсекаем пустые строки или комментарии с #
        SOURCES = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
else:
    # Если файла нет (например, кто-то скачал код с GitHub), скрипт просто получит пустой список
    SOURCES = []
