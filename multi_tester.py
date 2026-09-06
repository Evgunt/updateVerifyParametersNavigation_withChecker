import json
import os
import re
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs, unquote
import requests

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
XRAY_PATH = "./xray/xray.exe"
LOCAL_PORT_START = 10800
OUTPUT_FILENAME = "fast_vless.txt"
MAX_THREADS = 300

GIT_BRANCH = "main"
COMMIT_MESSAGE = "Auto-update: 60 fast configs"
REPO_PATH = os.path.dirname(os.path.abspath(__file__))


def run_git_command(args):
    try:
        result = subprocess.run(
            args,
            cwd=REPO_PATH,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        print(result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        print(f"Ошибка Git при выполнении {' '.join(args)}:")
        print(f"Ошибка: {e.stderr.strip()}")
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

    pattern = r"((?:vless|ss|hysteria|hy2|hysteria2|trojan)://[^\s'\"<>]+)"

    for url in sources:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                continue

            found_links = re.findall(pattern, response.text)
            print(
                f"  - Найдено сырых ссылок в {url.split('/')[-1]}: {len(found_links)}"
            )

            for link in found_links:
                link = link.strip()
                if not link or link.startswith("#"):
                    continue

                link_lower = link.lower()
                allowed_protocols = (
                    "vless://",
                    "ss://",
                    "hysteria://",
                    "hysteria2://",
                    "hy2://",
                    "trojan://",
                )
                if not link_lower.startswith(allowed_protocols):
                    continue

                if any(
                    geo in link_lower
                    for geo in ["russia", "united states", "ukraine"]
                ):
                    continue

                valid_links.add(link)
        except Exception as e:
            print(f"  - Ошибка загрузки источника {url.split('/')[-1]}: {e}")

    return list(valid_links)


def parse_proxy_link(link):
    """Универсальный парсер для vless, trojan и shadowsocks."""
    try:
        parsed = urlparse(link)
        protocol = parsed.scheme.lower()
        name = unquote(parsed.fragment) if parsed.fragment else "Без имени"

        query_params = parse_qs(parsed.query)

        def get_param(key):
            return query_params.get(key, [None])[0]

        # Базовая структура
        data = {
            "protocol": protocol,
            "name": name,
            "address": parsed.hostname,
            "port": int(parsed.port) if parsed.port else 443,
        }

        if protocol == "vless" or protocol == "trojan":
            data.update(
                {
                    "id": parsed.username,
                    "encryption": get_param("encryption") or "none",
                    "security": get_param("security") or "none",
                    "sni": get_param("sni"),
                    "fp": get_param("fp") or "chrome",
                    "pbk": get_param("pbk"),
                    "sid": get_param("sid"),
                    "type": get_param("type") or "tcp",
                }
            )
        elif protocol == "ss":
            user_info = parsed.username
            if user_info and ":" not in user_info:
                try:
                    user_info += "=" * (-len(user_info) % 4)
                    user_info = base64.b64decode(user_info).decode("utf-8")
                except Exception:
                    pass

            if user_info and ":" in user_info:
                method, password = user_info.split(":", 1)
                data.update({"method": method, "password": password})
            else:
                return None

        return data
    except Exception:
        return None

def build_xray_config(server, local_port, config_filename):
    """Универсальный конфигуратор для Xray под разные протоколы."""
    outbound = {"protocol": server["protocol"], "settings": {}}

    if server["protocol"] == "vless":
        outbound["settings"] = {
            "vnext": [
                {
                    "address": server["address"],
                    "port": server["port"],
                    "users": [
                        {
                            "id": server["id"],
                            "encryption": server["encryption"],
                        }
                    ],
                }
            ]
        }
        outbound["streamSettings"] = {
            "network": server["type"],
            "security": server["security"],
        }
        if server["security"] == "reality":
            outbound["streamSettings"]["realitySettings"] = {
                "show": False,
                "fingerprint": server["fp"],
                "serverName": server["sni"] or "",
                "publicKey": server["pbk"] or "",
                "shortId": server["sid"] or "",
            }

    elif server["protocol"] == "trojan":
        outbound["settings"] = {
            "servers": [
                {
                    "address": server["address"],
                    "port": server["port"],
                    "password": server["id"],
                }
            ]
        }
        outbound["streamSettings"] = {
            "network": server["type"],
            "security": server["security"],
        }
        if server["security"] == "reality":
            outbound["streamSettings"]["realitySettings"] = {
                "show": False,
                "fingerprint": server["fp"],
                "serverName": server["sni"] or "",
                "publicKey": server["pbk"] or "",
                "shortId": server["sid"] or "",
            }

    elif server["protocol"] == "ss":
        outbound["settings"] = {
            "servers": [
                {
                    "address": server["address"],
                    "port": server["port"],
                    "method": server["method"],
                    "password": server["password"],
                }
            ]
        }

    config = {
        "inbounds": [
            {
                "port": local_port,
                "listen": "127.0.0.1",
                "protocol": "socks",
                "settings": {"udp": True},
            }
        ],
        "outbounds": [outbound],
    }

    with open(config_filename, "w") as f:
        json.dump(config, f, indent=4)


def test_single_proxy(link, task_index, thread_id):
    server_data = parse_proxy_link(link)
    if not server_data:
        return None

    if server_data["protocol"] in ["hysteria", "hysteria2", "hy2"]:
        return None

    local_port = LOCAL_PORT_START + thread_id
    config_filename = (
        f"temp_config_task_{task_index}_{uuid.uuid4().hex[:6]}.json"
    )

    build_xray_config(server_data, local_port, config_filename)

    process = None
    try:
        process = subprocess.Popen(
            [XRAY_PATH, "-c", config_filename],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.8)

        proxies = {
            "http": f"socks5h://127.0.0.1:{local_port}",
            "https": f"socks5h://127.0.0.1:{local_port}",
        }

        ping_result = None
        start_time = time.time()
        response = requests.get(
            "https://cp.cloudflare.com", proxies=proxies, timeout=3.5, verify=True
        )
        end_time = time.time()

        if response.status_code in (200, 204):
            ping_result = round((end_time - start_time) * 1000)

    except requests.exceptions.RequestException:
        pass
    finally:
        if process:
            try:
                process.kill()
                process.wait()
            except Exception:
                pass
        time.sleep(0.05)
        if os.path.exists(config_filename):
            try:
                os.remove(config_filename)
            except OSError:
                pass

    if ping_result is not None:
        return ping_result, link, server_data["name"]
    return None


def main():
    if not os.path.exists(XRAY_PATH):
        print(f"[-] Ошибка: Файл {XRAY_PATH} не найден в папке проекта!")
        return

    links = fetch_and_filter_links(SOURCES)
    print(f"[*] После очистки и фильтрации к тесту готово: {len(links)} ссылок")

    if not links:
        print("[-] Рабочих ссылок после фильтров не осталось.")
        return

    working_configs = []
    print(
        f"\n[*] Запуск многопоточного тестирования (Потоков: {MAX_THREADS})..."
    )
    print("-" * 75)

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {
            executor.submit(test_single_proxy, link, i, i % MAX_THREADS): link
            for i, link in enumerate(links)
        }

        done_count = 0
        for future in as_completed(futures):
            done_count += 1
            result = future.result()

            if result is not None:
                ping, link, name = result
                working_configs.append((ping, link))
                print(
                    f"[{done_count}/{len(links)}] успешно | {ping:<5} мс | {name}"
                )

    print("-" * 75)
    print(
        f"[*] Тестирование завершено. Успешных конфигураций: {len(working_configs)}"
    )

    # Сортировка списка кортежей (ping, link) по первому элементу (ping)
    working_configs.sort(key=lambda x: x[0])
    top_60 = working_configs[:60]

    try:
        with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
            for ping, link in top_60:
                f.write(f"{link}\n")
        print(
            f"[+] ТОП-60 самых быстрых прокси успешно сохранены в файл: {OUTPUT_FILENAME}"
        )
    except Exception as e:
        print(f"[-] Ошибка при записи в файл: {e}")

    push_to_git()


if __name__ == "__main__":
    main()
