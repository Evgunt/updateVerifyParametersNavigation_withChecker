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

# Порог одновременных опросов (для асинхронного sing-box можно ставить 300-500)
MAX_CONCURRENT_TESTS = 300

GIT_BRANCH = "main"
COMMIT_MESSAGE = "Auto-update: 60 fast configs via Sing-box"
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
    pattern = r"((?:vless|vmess|ss|trojan)://[^\s'\"<>]+)"

    for url in sources:
        try:
            response = httpx.get(url, timeout=10.0)
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
                    "trojan://",
                    "vmess://",
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
    """Парсер под формат данных ядра sing-box."""
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
            data.update(
                {
                    "uuid": parsed.username,
                    "security": get_param("security") or "none",
                    "network": get_param("type") or "tcp",
                    "sni": get_param("sni") or "",
                    "fp": get_param("fp") or "chrome",
                    "pbk": get_param("pbk") or "",
                    "sid": get_param("sid") or "",
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


def generate_singbox_config(servers_list):
    """Генерирует 1 общий JSON конфиг для sing-box."""
    inbounds = []
    outbounds = []

    for index, s in enumerate(servers_list):
        tag = f"proxy_{index}"
        local_port = LOCAL_PORT_START + index

        inbounds.append(
            {
                "type": "socks",
                "tag": f"in_{tag}",
                "listen": "127.0.0.1",
                "listen_port": local_port,
            }
        )

        outbound = {
            "type": s["protocol"],
            "tag": tag,
            "server": s["address"],
            "server_port": s["port"],
        }

        if s["protocol"] == "vless":
            outbound.update({"uuid": s["uuid"]})
            if s["security"] in ["tls", "reality"]:
                tls_block = {"enabled": True, "server_name": s["sni"]}
                if s["security"] == "reality":
                    tls_block["reality"] = {
                        "enabled": True,
                        "public_key": s["pbk"],
                        "short_id": s["sid"],
                    }
                outbound["tls"] = tls_block

        elif s["protocol"] == "trojan":
            outbound["password"] = s["uuid"]
            if s["security"] in ["tls", "reality"]:
                tls_block = {"enabled": True, "server_name": s["sni"]}
                if s["security"] == "reality":
                    tls_block["reality"] = {
                        "enabled": True,
                        "public_key": s["pbk"],
                        "short_id": s["sid"],
                    }
                outbound["tls"] = tls_block

        elif s["protocol"] == "vmess":
            outbound.update({"uuid": s["uuid"], "security": "auto"})
            if s["security"] == "tls":
                outbound["tls"] = {"enabled": True, "server_name": s["sni"]}
            if s["network"] == "ws":
                outbound["transport"] = {
                    "type": "ws",
                    "path": s["path"],
                    "headers": {"Host": s["sni"] or s["host"]},
                }

        elif s["protocol"] == "ss":
            outbound.update({"method": s["method"], "password": s["password"]})

        outbounds.append(outbound)

    config = {"inbounds": inbounds, "outbounds": outbounds}

    with open(SINGBOX_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

async def test_url_via_socks(local_port, link, name, semaphore):
    """Асинхронный HTTP-запрос через заданный Socks5-порт."""
    async with semaphore:
        proxy_url = f"socks5://127.0.0.1:{local_port}"
        start_time = time.time()
        try:
            async with httpx.AsyncClient(
                proxies=proxy_url, timeout=3.5, verify=True
            ) as proxy_client:
                # Используем стабильный generate_204 от Google
                response = await proxy_client.get(
                    "https://cp.cloudflare.com"
                )
                if response.status_code in (200, 204):
                    ping = round((time.time() - start_time) * 1000)
                    return ping, link, name
        except Exception:
            pass
        return None


async def main_async():
    # 1. Тотальная приборка в системе от деда перед тестом
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
        print(
            f"[-] Ошибка: Ядро {SINGBOX_PATH} не найдено. Пожалуйста, скачайте его с GitHub."
        )
        return

    links = fetch_and_filter_links(SOURCES)
    if not links:
        print("[-] Нет доступных ссылок для тестов.")
        return

    parsed_servers = []
    for link in links:
        data = parse_proxy_link(link)
        if data:
            parsed_servers.append((link, data))

    print(f"[*] Успешно распарсено конфигураций: {len(parsed_servers)}")

    singbox_proc = None
    try:
        # Генерируем единственный файл конфигурации
        generate_singbox_config([data for _, data in parsed_servers])

        print("[*] Инициализация единого процесса Sing-box...")
        singbox_proc = subprocess.Popen(
            [SINGBOX_PATH, "run", "-c", SINGBOX_CONFIG],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Выделяем время на поднятие портов
        await asyncio.sleep(1.5)

        working_configs = []
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_TESTS)

        print(f"[*] Запуск массового асинхронного опроса прокси...")
        print("-" * 75)

        tasks = []
        for index, (link, data) in enumerate(parsed_servers):
            local_port = LOCAL_PORT_START + index
            tasks.append(
                test_url_via_socks(local_port, link, data["name"], semaphore)
            )

        results = await asyncio.gather(*tasks)

        for res in results:
            if res:
                ping, link, name = res
                working_configs.append((ping, link))
                print(f"[Успешно] | {ping:<5} мс | {name}")

        print("-" * 75)
        print(f"[*] Сбор данных завершен. Рабочих: {len(working_configs)}")

        working_configs.sort(key=lambda x: x[0])
        top_60 = working_configs[:60]

        try:
            with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
                for ping, link in top_60:
                    f.write(f"{link}\n")
            print(
                f"[+] Топ-60 результатов сохранены в файл: {OUTPUT_FILENAME}"
            )
        except Exception as e:
            print(f"[-] Ошибка сохранения результатов: {e}")

        push_to_git()

    finally:
        # 2. Финальная приборка: уничтожаем процесс ядра и ГАРАНТИРОВАННО стираем файл конфига
        print("[*] Очистка временных файлов и закрытие процессов...")
        if singbox_proc:
            try:
                singbox_proc.kill()
                singbox_proc.wait()
            except Exception:
                pass

        if os.path.exists(SINGBOX_CONFIG):
            try:
                os.remove(SINGBOX_CONFIG)
                print(f"[+] Временный файл {SINGBOX_CONFIG} успешно удален.")
            except OSError as e:
                print(f"[-] Предупреждение: Не удалось удалить файл: {e}")


if __name__ == "__main__":
    asyncio.run(main_async())
