import os
import re
import json
import time
import base64
import asyncio
import subprocess
from urllib.parse import urlparse, parse_qs, unquote

import httpx

SOURCES = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS.txt",
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/refs/heads/main/data/githubmirror/clean/vless.txt",
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/refs/heads/main/data/githubmirror/clean/trojan.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/1.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/2.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/3.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/4.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/5.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/6.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/7.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/8.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/9.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/10.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/11.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/12.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/13.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/14.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/15.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/16.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/17.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/18.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/19.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/20.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/21.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/22.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/23.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/24.txt",
    "https://raw.githubusercontent.com/hiztin/VLESS-PO-GRIBI/main/deploy/subscriptions/25.txt",
]
# ============================================================
# SETTINGS
# ============================================================
# ============================================================
# SETTINGS
# ============================================================

SINGBOX_PATH = "./singBox/sing-box.exe"
SINGBOX_CONFIG = "sing_box_config.json"

LOCAL_PORT_START = 10800

OUTPUT_FILENAME = "fast_vless.txt"

# Сколько конфигов загружаем в одну конфигурацию Sing-box.
BATCH_SIZE = 300

# Сколько прокси одновременно проверяем.
MAX_CONCURRENT_TESTS = 30

# Жесткий таймаут ОДНОГО прокси целиком.
PROXY_TIMEOUT = 6.0

# Максимальное время всей пачки.
BATCH_TIMEOUT = 25.0

# HTTP timeout должен быть меньше PROXY_TIMEOUT.
HTTP_CONNECT_TIMEOUT = 2.5
HTTP_READ_TIMEOUT = 2.5
HTTP_WRITE_TIMEOUT = 2.5
HTTP_POOL_TIMEOUT = 1.0

# Сколько ждать после запуска Sing-box.
SINGBOX_START_DELAY = 1.5

# Сколько ждать после убийства Sing-box.
CLEANUP_DELAY = 0.5

# Повторные попытки отключаем.
# Для массового тестера это сильно ускоряет обработку.
RETRY_COUNT = 0

# Сколько рабочих конфигов достаточно найти.
TARGET_WORKING = 60

# Используем очень лёгкий endpoint.
TEST_URLS = [
    "https://www.google.com/generate_204",
]

GIT_BRANCH = "main"

COMMIT_MESSAGE = (
    "Auto-update: 60 fast configs via Sing-box"
)

REPO_PATH = os.path.dirname(
    os.path.abspath(__file__)
)


# ============================================================
# GIT
# ============================================================

def run_git_command(args):
    try:
        result = subprocess.run(
            args,
            cwd=REPO_PATH,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        output = result.stdout.strip()
        if output:
            print(output)
        return True
    except subprocess.TimeoutExpired:
        print(f"Ошибка Git: команда зависла: {' '.join(args)}")
        return False
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        print(f"Ошибка Git при выполнении {' '.join(args)}: {stderr}")
        return False
    except Exception as e:
        print(f"Ошибка Git: {e}")
        return False


def push_to_git():
    print("\n--- Запуск синхронизации с Git ---")
    if not run_git_command(["git", "add", OUTPUT_FILENAME]):
        return

    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_PATH,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if not status.stdout.strip():
            print("Изменений в файле нет, Git push отменен.")
            return
    except Exception as e:
        print(f"[!] Не удалось проверить Git status: {e}")
        return

    if not run_git_command(["git", "commit", "-m", COMMIT_MESSAGE]):
        return

    if run_git_command(["git", "push", "origin", GIT_BRANCH]):
        print("[+] Данные успешно отправлены в репозиторий GitHub!")
    else:
        print("[-] Не удалось отправить данные в GitHub.")


# ============================================================
# PROCESS CLEANUP
# ============================================================

def kill_process_tree(proc=None):
    """
    Убивает конкретный Sing-box и его дочерние процессы.
    После этого дополнительно убивает все sing-box.exe.
    """
    if proc is not None:
        try:
            if proc.poll() is None:
                print(f"[i] Завершение Sing-box PID={proc.pid}...")
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/f", "/t", "/pid", str(proc.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=10,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
        except Exception as e:
            print(f"[!] Ошибка завершения PID: {e}")

        try:
            proc.wait(timeout=5)
        except Exception:
            pass

    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/f", "/t", "/im", "sing-box.exe"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            pass


def kill_old_vpn_processes():
    print("[*] Очистка старых VPN-процессов...")
    if os.name != "nt":
        return

    for proc_name in ["xray.exe", "sing-box.exe"]:
        try:
            subprocess.run(
                ["taskkill", "/f", "/t", "/im", proc_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            pass


async def cleanup_after_batch(proc):
    kill_process_tree(proc)
    await asyncio.sleep(CLEANUP_DELAY)

# ============================================================
# DOWNLOAD CONFIGS
# ============================================================

def fetch_and_filter_links(sources):
    valid_links = set()
    print("[*] Скачивание конфигураций из источников...")
    pattern = r"((?:vless|vmess|trojan|ss)://[^\s'\"<>]+)"

    for url in sources:
        try:
            response = httpx.get(url, timeout=15.0, follow_redirects=True)
            if response.status_code != 200:
                print(f"  - HTTP {response.status_code}: {url}")
                continue

            found_links = re.findall(pattern, response.text, flags=re.IGNORECASE)
            print(f"  - Найдено ссылок в {url.split('/')[-1]}: {len(found_links)}")

            for link in found_links:
                link = link.strip()
                if not link or link.startswith("#"):
                    continue

                link_lower = link.lower()
                allowed_protocols = ("vless://", "ss://", "trojan://", "vmess://")
                if not link_lower.startswith(allowed_protocols):
                    continue

                if any(geo in link_lower for geo in ["russia", "united states", "ukraine"]):
                    continue

                valid_links.add(link)
        except Exception as e:
            print(f"  - Ошибка загрузки {url.split('/')[-1]}: {e}")

    return list(valid_links)


# ============================================================
# PARSER
# ============================================================

def parse_proxy_link(link):
    try:
        link_lower = link.lower()

        if link_lower.startswith("vmess://"):
            b64_content = link[8:].strip()
            b64_content += "=" * (-len(b64_content) % 4)
            json_str = base64.b64decode(b64_content).decode("utf-8", errors="ignore")
            c = json.loads(json_str)

            return {
                "protocol": "vmess",
                "name": c.get("ps", "Без имени"),
                "address": c.get("add"),
                "port": int(c.get("port", 443)),
                "uuid": c.get("id"),
                "security": c.get("tls") or "none",
                "network": c.get("net", "tcp"),
                "path": c.get("path", ""),
                "sni": c.get("sni") or c.get("host") or "",
            }

        parsed = urlparse(link)
        protocol = parsed.scheme.lower()
        name = unquote(parsed.fragment) if parsed.fragment else "Без имени"
        query_params = parse_qs(parsed.query, keep_blank_values=True)

        def get_param(key):
            return query_params.get(key, [None])[0]

        data = {
            "protocol": protocol,
            "name": name,
            "address": parsed.hostname,
            "port": int(parsed.port) if parsed.port else 443,
        }

        if protocol in ["vless", "trojan"]:
            data.update({
                "uuid": parsed.username,
                "security": get_param("security") or "none",
                "network": get_param("type") or "tcp",
                "sni": get_param("sni") or "",
                "fp": get_param("fp") or "chrome",
                "pbk": get_param("pbk") or "",
                "sid": get_param("sid") or "",
                "flow": get_param("flow") or "",
            })

        return data
    except Exception:
        return None


# ============================================================
# VALIDATE SERVER
# ============================================================

def is_supported_server(data):
    if not data:
        return False

    protocol = data.get("protocol")
    if protocol not in ["vless", "vmess", "trojan"]:
        return False

    if not data.get("address") or not data.get("port"):
        return False

    if protocol in ["vless", "trojan"]:
        if not data.get("uuid"):
            return False

        if data.get("security") == "reality":
            pub_key = data.get("pbk", "").strip()
            if len(pub_key) != 43:
                return False

    if protocol == "vmess" and not data.get("uuid"):
        return False

    return True


# ============================================================
# SING-BOX OUTBOUND BUILDER
# ============================================================

def build_outbound(data, tag):
    protocol = data["protocol"]
    outbound = {
        "type": protocol,
        "tag": tag,
        "server": data["address"],
        "server_port": data["port"],
    }
    allowed_fingerprints = ["chrome", "firefox", "safari", "edge", "android", "ios"]

    # --------------------------------------------------------
    # VLESS
    # --------------------------------------------------------
    if protocol == "vless":
        outbound["uuid"] = data["uuid"]
        if "vision" in data.get("flow", ""):
            outbound["flow"] = "xtls-rprx-vision"

        if data.get("security") in ["tls", "reality"]:
            tls_block = {"enabled": True}
            if data.get("sni"):
                tls_block["server_name"] = data["sni"]

            fp_value = (data.get("fp") or "chrome").lower()
            if fp_value not in allowed_fingerprints:
                fp_value = "chrome"

            tls_block["utls"] = {"enabled": True, "fingerprint": fp_value}
            tls_block["fragment"] = True

            if data.get("security") == "reality":
                tls_block["reality"] = {
                    "enabled": True,
                    "public_key": data.get("pbk", "").strip(),
                    "short_id": data.get("sid", "").strip(),
                }
            outbound["tls"] = tls_block

    # --------------------------------------------------------
    # TROJAN
    # --------------------------------------------------------
    elif protocol == "trojan":
        outbound["password"] = data["uuid"]
        if data.get("security") in ["tls", "reality"]:
            tls_block = {"enabled": True}
            if data.get("sni"):
                tls_block["server_name"] = data["sni"]

            fp_value = (data.get("fp") or "chrome").lower()
            if fp_value not in allowed_fingerprints:
                fp_value = "chrome"

            tls_block["utls"] = {"enabled": True, "fingerprint": fp_value}
            tls_block["fragment"] = True

            if data.get("security") == "reality":
                tls_block["reality"] = {
                    "enabled": True,
                    "public_key": data.get("pbk", "").strip(),
                    "short_id": data.get("sid", "").strip(),
                }
            outbound["tls"] = tls_block

    # --------------------------------------------------------
    # VMESS
    # --------------------------------------------------------
    elif protocol == "vmess":
        outbound.update({"uuid": data["uuid"], "security": "auto"})
        if data.get("security") == "tls":
            tls_block = {"enabled": True}
            if data.get("sni"):
                tls_block["server_name"] = data["sni"]
            tls_block["fragment"] = True
            outbound["tls"] = tls_block

        if data.get("network") == "ws":
            host_header = data.get("sni") or data.get("host") or data["address"]
            outbound["transport"] = {
                "type": "ws",
                "path": data.get("path", ""),
                "headers": {"Host": host_header},
            }

    return outbound


# ============================================================
# GENERATE SING-BOX CONFIG
# ============================================================

def generate_singbox_config(servers_list):
    inbounds = []
    outbounds = []
    rules = []
    valid_servers = []

    for link, data in servers_list:
        if not is_supported_server(data):
            continue
        valid_servers.append((link, data))

    for index, (link, data) in enumerate(valid_servers):
        tag = f"proxy_{index}"
        inbound_tag = f"in_{tag}"
        local_port = LOCAL_PORT_START + index

        inbounds.append({
            "type": "socks",
            "tag": inbound_tag,
            "listen": "127.0.0.1",
            "listen_port": local_port,
        })
        outbounds.append(build_outbound(data, tag))
        rules.append({"inbound": [inbound_tag], "outbound": tag})

    config = {
        "log": {"level": "error"},
        "dns": {
            "servers": [{"type": "udp", "tag": "dns_direct", "server": "1.1.1.1"}]
        },
        "inbounds": inbounds,
        "outbounds": outbounds,
        "route": {"rules": rules},
    }

    with open(SINGBOX_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    return valid_servers


# ============================================================
# TEST ONE PROXY
# ============================================================
async def test_one_proxy(local_port, link, name,):
    proxy_url = (
        f"socks5://127.0.0.1:{local_port}"
    )

    timeout = httpx.Timeout(
        connect=HTTP_CONNECT_TIMEOUT,
        read=HTTP_READ_TIMEOUT,
        write=HTTP_WRITE_TIMEOUT,
        pool=HTTP_POOL_TIMEOUT,
    )

    async def do_request():
        start_time = time.monotonic()
        async with httpx.AsyncClient(
            proxy=proxy_url,
            timeout=timeout,
            verify=False,
            follow_redirects=False,
            limits=httpx.Limits(
                max_connections=1,
                max_keepalive_connections=0,
            ),
        ) as client:

            for test_url in TEST_URLS:
                response = await client.get(test_url)
                if response.status_code in (200, 204,):
                    ping = round((time.monotonic() - start_time) * 1000)

                    return (ping, link, name)
        return None

    try:
        # ----------------------------------------------------
        # Жесткий timeout на весь прокси.
        # ----------------------------------------------------
        return await asyncio.wait_for(
            do_request(),
            timeout=PROXY_TIMEOUT,
        )

    except asyncio.TimeoutError:
        return None
    except asyncio.CancelledError:
        raise
    except (
        httpx.ProxyError,
        httpx.ConnectError,
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
        httpx.WriteTimeout,
        httpx.PoolTimeout,
        httpx.RemoteProtocolError,
        httpx.NetworkError,
    ):
        return None
    except Exception:
        return None


# ============================================================
# TEST BATCH
# ============================================================

async def test_batch(
    valid_servers,
    batch_number,
    total_batches,
):
    """
    Проверяет пачку прокси.

    Здесь принципиально НЕ используется обычный
    asyncio.gather() на все 300 задач с бесконечным ожиданием.

    Одновременно работают только MAX_CONCURRENT_TESTS
    соединений.

    Каждый отдельный прокси имеет PROXY_TIMEOUT.

    Вся пачка имеет BATCH_TIMEOUT.
    """

    total = len(valid_servers)

    if total == 0:
        return []

    semaphore = asyncio.Semaphore(
        MAX_CONCURRENT_TESTS
    )

    results = []

    completed = 0

    started = time.monotonic()

    print(
        f"[i] Пачка "
        f"{batch_number}/{total_batches}: "
        f"{total} тестов, "
        f"одновременно "
        f"{MAX_CONCURRENT_TESTS}"
    )

    async def worker(
        index,
        link,
        data,
    ):

        async with semaphore:

            local_port = (
                LOCAL_PORT_START + index
            )

            return await test_one_proxy(
                local_port,
                link,
                data.get(
                    "name",
                    "Без имени",
                ),
            )

    tasks = []

    # --------------------------------------------------------
    # Создаем задачи.
    #
    # Они сразу упираются в semaphore, поэтому одновременно
    # HTTP-соединений больше MAX_CONCURRENT_TESTS не будет.
    # --------------------------------------------------------

    for index, (link, data) in enumerate(
        valid_servers
    ):

        task = asyncio.create_task(
            worker(
                index,
                link,
                data,
            )
        )

        tasks.append(task)

    try:

        # ----------------------------------------------------
        # Ждем результаты по мере завершения.
        #
        # Это лучше обычного gather для нашего тестера:
        # быстрые прокси не ждут медленные.
        # ----------------------------------------------------

        for future in asyncio.as_completed(
            tasks,
            timeout=BATCH_TIMEOUT,
        ):

            try:

                result = await future

            except asyncio.CancelledError:

                raise

            except Exception:

                result = None

            completed += 1

            if result:

                ping, link, name = result

                results.append(result)

                print(
                    f"[OK] "
                    f"{completed:>3}/{total:<3} | "
                    f"{ping:>5} мс | "
                    f"{name}"
                )

            else:

                print(
                    f"[--] "
                    f"{completed:>3}/{total:<3}",
                    end="\r",
                    flush=True,
                )

            # ------------------------------------------------
            # Если уже получили достаточно рабочих,
            # остальные тесты можно прекратить.
            # ------------------------------------------------

            if (
                TARGET_WORKING > 0
                and len(results)
                >= TARGET_WORKING
            ):

                print()

                print(
                    "[i] Уже найдено "
                    f"{len(results)} рабочих. "
                    "Останавливаем оставшиеся тесты."
                )

                break

    except asyncio.TimeoutError:

        elapsed = round(
            time.monotonic() - started,
            1,
        )

        print()

        print(
            f"[!] Таймаут пачки "
            f"{batch_number}: "
            f"{elapsed} сек."
        )

        print(
            f"[!] Завершено: "
            f"{completed}/{total}. "
            "Отменяем оставшиеся задачи..."
        )

    finally:

        # ----------------------------------------------------
        # КРИТИЧЕСКИ ВАЖНО
        #
        # Отменяем ВСЕ незавершенные задачи.
        # ----------------------------------------------------

        pending = [
            task
            for task in tasks
            if not task.done()
        ]

        if pending:

            for task in pending:
                task.cancel()

            await asyncio.gather(
                *pending,
                return_exceptions=True,
            )

        # ----------------------------------------------------
        # Собираем результаты, которые уже успели завершиться,
        # но могли не попасть в as_completed.
        # ----------------------------------------------------

        for task in tasks:

            if not task.done():
                continue

            if task.cancelled():
                continue

            try:

                result = task.result()

            except Exception:

                continue

            if result is None:
                continue

            # Не добавляем дубликаты.
            if result not in results:
                results.append(result)

    print()

    print(
        f"[i] Пачка "
        f"{batch_number} завершена: "
        f"{len(results)} рабочих."
    )

    return results


# ============================================================
# START SING-BOX
# ============================================================

def start_singbox():
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        proc = subprocess.Popen(
            [SINGBOX_PATH, "run", "-c", SINGBOX_CONFIG],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            start_new_session=(os.name != "nt"),
        )
        return proc
    except Exception as e:
        print(f"[-] Не удалось запустить Sing-box: {e}")
        return None


# ============================================================
# CHECK SING-BOX CONFIG
# ============================================================

def check_singbox_config():
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        result = subprocess.run(
            [SINGBOX_PATH, "check", "-c", SINGBOX_CONFIG],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            creationflags=creationflags,
        )
        if result.returncode != 0:
            print("[-] Sing-box отклонил конфигурацию:")
            output = (result.stderr or result.stdout or "").strip()
            if output:
                print(output)
            return False
        return True
    except Exception as e:
        print(f"[-] Ошибка проверки конфига Sing-box: {e}")
        return False


# ============================================================
# SAVE RESULTS
# ============================================================

def modify_link_for_output(link):
    try:
        if "#" in link:
            main_part, name_part = link.split("#", 1)
        else:
            main_part = link
            name_part = ""

        query_lower = main_part.lower()
        if "?" in main_part:
            if not re.search(r"(?:[?&])fp=", query_lower):
                main_part += "&fp=chrome"
        else:
            main_part += "?fp=chrome"

        return f"{main_part}#{name_part}" if name_part else main_part
    except Exception:
        return link


def save_results(working_configs):
    working_configs.sort(key=lambda x: x[0])
    top_60 = working_configs[:60]

    try:
        with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
            for ping, link in top_60:
                modified_link = modify_link_for_output(link)
                f.write(f"{modified_link}\n")
        print(f"[+] ТОП-{len(top_60)} сохранен в {OUTPUT_FILENAME}")
        return True
    except Exception as e:
        print(f"[-] Ошибка записи результата: {e}")
        return False


# ============================================================
# MAIN
# ============================================================
async def main_async():
    kill_old_vpn_processes()

    if not os.path.exists(SINGBOX_PATH):
        print(f"[-] Ошибка: ядро {SINGBOX_PATH} не найдено.")
        return

    # --------------------------------------------------------
    # DOWNLOAD
    # --------------------------------------------------------
    links = fetch_and_filter_links(SOURCES)
    if not links:
        print("[-] Нет доступных ссылок для тестов.")
        return

    # --------------------------------------------------------
    # PARSE
    # --------------------------------------------------------
    parsed_servers = []
    seen = set()

    for link in links:
        data = parse_proxy_link(link)
        if not is_supported_server(data):
            continue

        unique_key = f"{data['protocol']}:{data['address']}:{data['port']}"
        if unique_key in seen:
            continue

        seen.add(unique_key)
        parsed_servers.append((link, data))

    total_proxies = len(parsed_servers)
    print(f"\n[*] Уникальных конфигураций: {total_proxies}")

    if not parsed_servers:
        print("[-] После парсинга конфигураций не осталось.")
        return

    working_configs = []
    total_batches = (total_proxies + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"[*] Пачек: {total_batches}")
    print(f"[*] Размер пачки: {BATCH_SIZE}")
    print(f"[*] Параллельных тестов: {MAX_CONCURRENT_TESTS}")
    print(f"[*] Timeout connect/read: {HTTP_CONNECT_TIMEOUT}/{HTTP_READ_TIMEOUT} сек.")

    # --------------------------------------------------------
    # BATCH LOOP
    # --------------------------------------------------------
    try:
        for batch_index in range(total_batches):
            if TARGET_WORKING > 0 and len(working_configs) >= TARGET_WORKING:
                print("\n[i] Найдено достаточно рабочих конфигураций.")
                break

            start_index = batch_index * BATCH_SIZE
            end_index = min(start_index + BATCH_SIZE, total_proxies)
            raw_batch = parsed_servers[start_index:end_index]
            batch_number = batch_index + 1

            print()
            print("=" * 75)
            print(f"[+] Пачка {batch_number}/{total_batches} | {start_index + 1}-{end_index} из {total_proxies}")

            # ------------------------------------------------
            # CLEANUP
            # ------------------------------------------------
            kill_old_vpn_processes()
            await asyncio.sleep(0.3)

            # ------------------------------------------------
            # CONFIG
            # ------------------------------------------------
            try:
                valid_servers = generate_singbox_config(raw_batch)
            except Exception as e:
                print(f"[-] Ошибка генерации конфига: {e}")
                continue

            valid_count = len(valid_servers)
            print(f"[i] Подходящих конфигов в пачке: {valid_count}")

            if valid_count == 0:
                print("[i] В пачке нет подходящих конфигураций.")
                continue

            # ------------------------------------------------
            # CHECK CONFIG
            # ------------------------------------------------
            if not check_singbox_config():
                print("[-] Пропускаем пачку.")
                continue

            # ------------------------------------------------
            # START
            # ------------------------------------------------
            singbox_proc = start_singbox()
            if singbox_proc is None:
                print("[-] Sing-box не запустился.")
                kill_old_vpn_processes()
                continue

            print(f"[i] Sing-box запущен. PID={singbox_proc.pid}")
            await asyncio.sleep(SINGBOX_START_DELAY)

            if singbox_proc.poll() is not None:
                print("[-] Sing-box завершился сразу после запуска.")
                kill_process_tree(singbox_proc)
                await asyncio.sleep(CLEANUP_DELAY)
                continue

            # ------------------------------------------------
            # TEST
            # ------------------------------------------------
            try:
                results = await test_batch(valid_servers, batch_number, total_batches)
            except asyncio.CancelledError:
                print("[!] Проверка отменена.")
                results = []
            except Exception as e:
                print(f"[-] Ошибка тестирование пачки: {e}")
                results = []

            # ------------------------------------------------
            # RESULTS
            # ------------------------------------------------
            batch_success = 0
            for result in results:
                if not result:
                    continue
                try:
                    ping, link, name = result
                    working_configs.append((ping, link))
                    batch_success += 1
                except Exception:
                    continue

            print(f"\n[i] Пачка {batch_number} завершена.")
            print(f"[i] Рабочих в пачке: {batch_success}")
            print(f"[i] Рабочих всего: {len(working_configs)}")

            # ------------------------------------------------
            # CLEANUP
            # ------------------------------------------------
            await cleanup_after_batch(singbox_proc)
            print("[i] Sing-box полностью остановлен.")

    except KeyboardInterrupt:
        print("\n[!] Получен Ctrl+C.")
    except Exception as e:
        print(f"\n[-] Критическая ошибка: {e}")
    finally:
        print("\n[*] Финальная очистка VPN-процессов...")
        kill_old_vpn_processes()

    # ========================================================
    # FINAL
    # ========================================================
    print()
    print("-" * 75)
    print("[*] Полное тестирование завершено!")
    print(f"[*] Проверено конфигураций: {total_proxies}")
    print(f"[*] Рабочих найдено: {len(working_configs)}")

    # --------------------------------------------------------
    # SAVE TOP 60
    # --------------------------------------------------------
    save_results(working_configs)

    # --------------------------------------------------------
    # GIT
    # --------------------------------------------------------
    push_to_git()

    # --------------------------------------------------------
    # DELETE TEMP CONFIG
    # --------------------------------------------------------
    if os.path.exists(SINGBOX_CONFIG):
        try:
            os.remove(SINGBOX_CONFIG)
            print(f"[+] Временный файл {SINGBOX_CONFIG} удален.")
        except OSError as e:
            print(f"[-] Не удалось удалить {SINGBOX_CONFIG}: {e}")

    print("\n[+] Работа завершена.")


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n[!] Программа остановлена пользователем.")
        kill_old_vpn_processes()
        os.remove(SINGBOX_CONFIG)
        print(f"[+] Временный файл {SINGBOX_CONFIG} удален.")
    except Exception as e:
        print(f"\n[-] Необработанная ошибка: {e}")
        kill_old_vpn_processes()
        os.remove(SINGBOX_CONFIG)
        print(f"[+] Временный файл {SINGBOX_CONFIG} удален.")
