import asyncio
import base64
import json
import os
import re
import subprocess
import time
from urllib.parse import parse_qs, unquote, urlparse
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
SINGBOX_PATH = "./singBox/sing-box.exe"
SINGBOX_CONFIG = "sing_box_config.json"
LOCAL_PORT_START = 10800
OUTPUT_FILENAME = "fast_vless.txt"

MAX_CONCURRENT_TESTS = 250  # Слегка снизим для стабильности на Windows сокетах
BATCH_SIZE = 500           # Оптимальный размер пачки

# MAX_CONCURRENT_TESTS = 50   # Не перегружаем сетевой стек
# BATCH_SIZE = 100            # Оптимальный размер пачки для Windows

GIT_BRANCH = "main"
COMMIT_MESSAGE = "Auto-update: 60 fast configs via Sing-box"
REPO_PATH = os.path.dirname(os.path.abspath(__file__))


def run_git_command(args):
    try:
        result = subprocess.run(
            args, cwd=REPO_PATH, capture_output=True, text=True, check=True, encoding="utf-8"
        )
        print(result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        print(f"Ошибка Git при выполнении {' '.join(args)}: {e.stderr.strip()}")
        return False


def push_to_git():
    print("\n--- Запуск синхронизации с Git ---")
    if not run_git_command(["git", "add", OUTPUT_FILENAME]):
        return
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=REPO_PATH, capture_output=True, text=True, check=True
        )
        if not status.stdout.strip():
            print("Изменений в файле нет, Git push отменен.")
            return
    except Exception:
        pass

    if not run_git_command(["git", "commit", "-m", COMMIT_MESSAGE]):
        return

    if run_git_command(["git", "push", "origin", GIT_BRANCH]):
        print("Данные успешно отправлены в репозиторий GitHub!")
    else:
        print("Не удалось отправить данные в GitHub.")


def fetch_and_filter_links(sources):
    valid_links = set()
    print("[*] Скачивание конфигураций из источников...")
    pattern = r"((?:vless|vmess|trojan)://[^\s'\"<>]+)"

    for url in sources:
        try:
            response = httpx.get(url, timeout=15.0)
            if response.status_code != 200:
                continue

            found_links = re.findall(pattern, response.text)
            print(f"  - Найдено сырых ссылок в {url.split('/')[-1]}: {len(found_links)}")

            for link in found_links:
                link = link.strip()
                if not link or link.startswith("#"):
                    continue

                link_lower = link.lower()
                allowed_protocols = ("vless://", "ss://", "trojan://", "vmess://")
                if not link_lower.startswith(allowed_protocols):
                    continue
                
                # Исключаем явные метрики локальных регионов, если это необходимо
                if any(geo in link_lower for geo in ["russia", "united states", "ukraine"]):
                    continue

                valid_links.add(link)
        except Exception as e:
            print(f"  - Ошибка загрузки источника {url.split('/')[-1]}: {e}")

    return list(valid_links)


def parse_proxy_link(link):
    try:
        link_lower = link.lower()

        if link_lower.startswith("vmess://"):
            b64_content = link[8:].strip()
            b64_content += "=" * (-len(b64_content) % 4)
            json_str = base64.b64decode(b64_content).decode("utf-8")
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
        query_params = parse_qs(parsed.query)

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
                "flow": get_param("flow") or ""
            })

        return data
    except Exception:
        return None


def generate_singbox_config(servers_list):
    """Генерирует чистый JSON конфиг для VLESS, Trojan и VMess, полностью исключая Shadowsocks."""
    inbounds = []
    outbounds = []

    # Список разрешенных uTLS отпечатков для ядра sing-box
    ALLOWED_FINGERPRINTS = ["chrome", "firefox", "safari", "edge", "android", "ios"]

    for index, s in enumerate(servers_list):
        if not s or "protocol" not in s or not s.get("address"):
            continue
            
        # Полностью игнорируем протокол shadowsocks, если он случайно проскочит
        if s["protocol"] == "ss":
            continue

        tag = f"proxy_{index}"
        local_port = LOCAL_PORT_START + index

        current_inbound = {
            "type": "socks",
            "tag": f"in_{tag}",
            "listen": "127.0.0.1",
            "listen_port": local_port,
        }

        outbound = {
            "type": s["protocol"],
            "tag": tag,
            "server": s["address"],
            "server_port": s["port"],
        }

        skip_node = False

        # --- НАСТРОЙКА VLESS ---
        if s["protocol"] == "vless":
            outbound["uuid"] = s["uuid"]
            if "vision" in s.get("flow", ""):
                outbound["flow"] = "xtls-rprx-vision"

            if s["security"] in ["tls", "reality"]:
                tls_block = {"enabled": True}
                if s.get("sni"):
                    tls_block["server_name"] = s["sni"]

                fp_value = (s.get("fp") or "chrome").lower()
                if fp_value not in ALLOWED_FINGERPRINTS:
                    fp_value = "chrome"

                tls_block["utls"] = {"enabled": True, "fingerprint": fp_value}
                tls_block["fragment"] = True

                if s["security"] == "reality":
                    pub_key = s.get("pbk", "").strip()
                    if not pub_key or len(pub_key) != 43:
                        skip_node = True
                        continue

                    tls_block["reality"] = {
                        "enabled": True,
                        "public_key": pub_key,
                        "short_id": s.get("sid", "").strip(),
                    }
                outbound["tls"] = tls_block

        # --- НАСТРОЙКА TROJAN ---
        elif s["protocol"] == "trojan":
            outbound["password"] = s["uuid"]
            if s["security"] in ["tls", "reality"]:
                tls_block = {"enabled": True}
                if s.get("sni"):
                    tls_block["server_name"] = s["sni"]

                fp_value = (s.get("fp") or "chrome").lower()
                if fp_value not in ALLOWED_FINGERPRINTS:
                    fp_value = "chrome"

                tls_block["utls"] = {"enabled": True, "fingerprint": fp_value}
                tls_block["fragment"] = True

                if s["security"] == "reality":
                    pub_key = s.get("pbk", "").strip()
                    if not pub_key or len(pub_key) != 43:
                        skip_node = True
                        continue

                    tls_block["reality"] = {
                        "enabled": True,
                        "public_key": pub_key,
                        "short_id": s.get("sid", "").strip(),
                    }
                outbound["tls"] = tls_block

        # --- НАСТРОЙКА VMESS ---
        elif s["protocol"] == "vmess":
            outbound.update({"uuid": s["uuid"], "security": "auto"})
            if s["security"] == "tls":
                outbound["tls"] = {
                    "enabled": True, 
                    "server_name": s.get("sni", ""),
                    "fragment": True
                }

            if s["network"] == "ws":
                host_header = s.get("sni") or s.get("host") or s["address"]
                outbound["transport"] = {
                    "type": "ws",
                    "path": s.get("path", ""),
                    "headers": {"Host": host_header},
                }

        if not skip_node:
            inbounds.append(current_inbound)
            outbounds.append(outbound)

    # Чистая конфигурация без лишних direct-выходов
    config = {
        "log": {"level": "error"},
        "dns": {
            "servers": [
                {
                    "type": "udp",
                    "tag": "dns_direct",
                    "server": "1.1.1.1"
                }
            ]
        },
        "inbounds": inbounds,
        "outbounds": outbounds,
        "route": {
            "rules": [
                {"inbound": [f"in_proxy_{i}"], "outbound": f"proxy_{i}"}
                for i in range(len(outbounds))
            ]
        },
    }

    with open(SINGBOX_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)


async def test_url_via_socks(local_port, link, name, semaphore):
    """Асинхронный HTTP-запрос через Socks5-порт с исправленным синтаксисом httpx 2026 года."""
    async with semaphore:
        proxy_url = f"socks5://127.0.0.1:{local_port}"
        
        for attempt in range(2):
            start_time = time.time()
            try:
                # ИСПРАВЛЕНО: 'proxy' вместо 'proxies' для совместимости с новыми версиями httpx
                async with httpx.AsyncClient(proxy=proxy_url, timeout=10.0, verify=False) as proxy_client:
                    # Используем легкий и стабильный эндпоинт
                    response = await proxy_client.get("https://httpbin.org", follow_redirects=True)
                    
                    if response.status_code == 200:
                        ping = round((time.time() - start_time) * 1000)
                        return ping, link, name
            except (httpx.ProxyError, httpx.ConnectError):
                # Если порт под нагрузкой еще не открылся, ждем 0.5 сек и пробуем финальный раз
                if attempt == 0:
                    await asyncio.sleep(0.5)
                    continue
            except Exception:
                # Полностью глушим остальные ошибки, чтобы не спамить и не вешать консоль
                pass
        return None

async def main_async():
    print("[*] Предварительное уничтожение зависших процессов VPN-ядер...")
    for proc_name in ["xray.exe", "sing-box.exe"]:
        try:
            subprocess.run(
                ["taskkill", "/f", "/im", proc_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    if not os.path.exists(SINGBOX_PATH):
        print(f"[-] Ошибка: Ядро {SINGBOX_PATH} не найдено.")
        return

    links = fetch_and_filter_links(SOURCES)
    if not links:
        print("[-] Нет доступных ссылок для тестов.")
        return

    parsed_servers = []
    seen_addresses = set()
    for link in links:
        data = parse_proxy_link(link)
        if data and data.get("address"):
            unique_key = f"{data['protocol']}_{data['address']}_{data['port']}"
            if unique_key not in seen_addresses:
                seen_addresses.add(unique_key)
                parsed_servers.append((link, data))

    total_proxies = len(parsed_servers)
    print(f"[*] Успешно распарсено уникальных конфигураций: {total_proxies}")

    working_configs = []
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TESTS)

    print(f"[*] Запуск циклического тестирования пачками по {BATCH_SIZE} штук...")

    try:
        for i in range(0, total_proxies, BATCH_SIZE):
            batch = parsed_servers[i : i + BATCH_SIZE]
            print(f"\n[+] Тестирование пачки {i // BATCH_SIZE + 1} (Прокси с {i} по {i + len(batch)} из {total_proxies})...")

            generate_singbox_config([data for _, data in batch])

            # Запускаем Sing-box с захватом ошибок stderr
            singbox_proc = subprocess.Popen(
                [SINGBOX_PATH, "run", "-c", SINGBOX_CONFIG],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )

            # Выделяем время на прогрузку портов пачки и инициализацию TLS структур
            await asyncio.sleep(5.0)

            # Если ядро вылетело — пишем ошибку и скипаем пачку
            if singbox_proc.poll() is not None:
                print(f"[-] Ошибка: Sing-box упал при старте пачки!")
                print(f"[Логи ядра]:\n{singbox_proc.stderr.read()}")
                continue

            tasks = []
            for local_index, (link, data) in enumerate(batch):
                local_port = LOCAL_PORT_START + local_index
                tasks.append(
                    test_url_via_socks(local_port, link, data["name"], semaphore)
                )

            results = await asyncio.gather(*tasks)

            batch_success = 0
            for res in results:
                if res:
                    ping, link, name = res
                    working_configs.append((ping, link))
                    batch_success += 1
                    print(f"[Успешно] | {ping:<5} мс | {name}")

            print(f"[i] Пачка завершена. Найдено рабочих в этой пачке: {batch_success}")

            # Жестко тушим конкретный процесс этой пачки по PID, чтобы он не остался в памяти Windows
            try:
                if singbox_proc.poll() is None: # Если процесс еще живой
                    subprocess.run(
                        ["taskkill", "/f", "/pid", str(singbox_proc.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                singbox_proc.wait()
            except Exception:
                pass

        print("-" * 75)
        print(f"[*] Полное тестирование завершено! Проверено: {total_proxies}. Рабочих всего: {len(working_configs)}")

        working_configs.sort(key=lambda x: x)
        top_60 = working_configs[:60]

        try:
            with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
                for ping, link in top_60:
                    # Модифицируем ссылку, добавляя параметры фрагментации для клиентов
                    modified_link = link
                    try:
                        # Разделяем ссылку на основную часть и фрагмент (имя после #)
                        if "#" in link:
                            main_part, name_part = link.split("#", 1)
                        else:
                            main_part, name_part = link, ""

                        # Проверяем, есть ли уже query-параметры
                        if "?" in main_part:
                            # Добавляем параметры к существующим
                            # Некоторые клиенты читают фрагментацию через дефолтные пропсы, 
                            # v2rayNG/NekoBox поддерживают чтение встроенных параметров у некоторых ядер
                            if "fp=" not in main_part:
                                main_part += "&fp=chrome"
                        else:
                            main_part += "?fp=chrome"

                        # Интегрируем указание для современных GUI-клиентов на использование фрагментов.
                        # Формат подмешивания кастомных флагов может отличаться для разных клиентов,
                        # но добавление флага uTLS (fp=chrome) гарантирует эмуляцию во всех приложениях.
                        
                        modified_link = f"{main_part}#{name_part}" if name_part else main_part
                    except Exception:
                        pass # Если не удалось распарсить, оставляем ссылку как есть

                    f.write(f"{modified_link}\n")
            print(f"[+] ТОП-60 самых быстрых прокси успешно сохранены в файл: {OUTPUT_FILENAME}")
        except Exception as e:
            print(f"[-] Ошибка при записи в файл: {e}")
        
        push_to_git()

    finally:
        print("[*] Очистка временных файлов и закрытие процессов...")
        if os.path.exists(SINGBOX_CONFIG):
            try:
                os.remove(SINGBOX_CONFIG)
                print(f"[+] Временный файл {SINGBOX_CONFIG} успешно удален.")
            except OSError as e:
                print(f"[-] Предупреждение: Не удалось удалить файл: {e}")


if __name__ == "__main__":
    asyncio.run(main_async())
