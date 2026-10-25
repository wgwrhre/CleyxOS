"""Small built-in English/Turkish interface translations."""

from __future__ import annotations

import re

from core.config import get_config

SUPPORTED_LANGUAGES = {"en": "English", "tr": "Türkçe"}

_TRANSLATIONS = {
    "en": {
        "help_title": "CleyxOS Commands", "help_column": "Description",
        "help_hint": "Quote paths containing spaces. Filesystem commands operate on the paths you specify.",
        "language_usage": "Usage: language <en|tr>",
        "language_set": "Interface language set to {language}.",
        "language_current": "Current language: {language}. Available: en (English), tr (Türkçe).",
        "welcome": "Type 'help' to explore CleyxOS commands. Ctrl+C also exits the session.",
        "interrupted": "Use 'exit' to shut down CleyxOS.",
        "shutdown": "Shutting down CleyxOS.",
        "website_usage": "Usage: open <website>",
        "website_invalid": "Enter a valid website address (for example, example.com).",
        "website_opened": "Opening {url} in your default browser.",
        "app_not_found": "No matching application found for '{query}'.",
        "app_ambiguous": "Several applications match '{query}'. Be more specific:",
        "app_removed": "Removed registration for {name}.",
        "app_not_registered": "{name} is installed on this computer but is not registered. 'app remove' only removes CleyxOS registrations; it does not uninstall software.",
        "app_no_launch_target": "Found {name}, but could not locate a launchable application file.",
        "restart_shell": "Restarting the CleyxOS shell.",
        "timer_cancel": "Press Ctrl+C to cancel the timer.",
    },
    "tr": {
        "help_title": "CleyxOS Komutları", "help_column": "Açıklama",
        "help_hint": "Boşluk içeren yolları tırnak içine alın. Dosya komutları belirttiğiniz yollarda çalışır.",
        "language_usage": "Kullanım: language <en|tr>",
        "language_set": "Arayüz dili {language} olarak ayarlandı.",
        "language_current": "Geçerli dil: {language}. Seçenekler: en (English), tr (Türkçe).",
        "welcome": "CleyxOS komutlarını görmek için 'help' yazın. Ctrl+C ile de çıkabilirsiniz.",
        "interrupted": "CleyxOS'tan çıkmak için 'exit' yazın.",
        "shutdown": "CleyxOS kapatılıyor.",
        "website_usage": "Kullanım: open <website>",
        "website_invalid": "Geçerli bir web adresi girin (örnek: example.com).",
        "website_opened": "{url} varsayılan tarayıcınızda açılıyor.",
        "app_not_found": "'{query}' ile eşleşen uygulama bulunamadı.",
        "app_ambiguous": "'{query}' ile birden fazla uygulama eşleşti. Daha belirgin bir ad girin:",
        "app_removed": "{name} uygulama kaydı kaldırıldı.",
        "app_not_registered": "{name} bu bilgisayarda yüklü, ancak CleyxOS'a kayıtlı değil. 'app remove' yalnızca CleyxOS kayıtlarını kaldırır; uygulamayı kaldırmaz.",
        "app_no_launch_target": "{name} bulundu ancak başlatılabilir uygulama dosyası bulunamadı.",
        "restart_shell": "CleyxOS kabuğu yeniden başlatılıyor.",
        "timer_cancel": "Sayacı iptal etmek için Ctrl+C tuşlarına basın.",
    },
}

_DESCRIPTIONS_TR = {
    "help": "Kullanılabilir komutları göster", "clear": "Terminali temizle",
    "sysinfo": "CPU, RAM, GPU, işletim sistemi ve Python bilgilerini göster",
    "neofetch": "CleyxOS ve sistem bilgilerini göster", "uptime": "Oturum süresini göster",
    "processes": "Çalışan işlemleri listele", "performance": "CPU ve RAM kullanımını göster",
    "exit": "CleyxOS'tan çık", "ls": "Dosya ve klasörleri listele",
    "cd": "Geçerli klasörü değiştir", "pwd": "Geçerli klasörün yolunu göster",
    "mkdir": "Klasör oluştur", "touch": "Dosya oluştur", "cat": "Metin dosyasını oku",
    "cp": "Dosya veya klasörü kopyala", "mv": "Dosya veya klasörü taşı",
    "rm": "Onay alarak dosya veya klasörü sil", "time": "Saati göster", "date": "Tarihi göster",
    "calc": "Güvenli matematiksel ifade hesapla", "history": "Komut geçmişini göster",
    "echo": "Metni yazdır", "ping": "Belirtilen sunucuya bağlantıyı dene",
    "weather": "Bir şehir için güncel hava durumunu göster", "apps": "Kayıtlı uygulamaları listele",
    "app add": "Python betiği veya Windows uygulaması kaydet",
    "app run": "Kayıtlı veya yüklü uygulamayı başlat",
    "app remove": "CleyxOS uygulama kaydını kaldır", "app info": "Uygulama bilgilerini göster",
    "open": "Web sitesini varsayılan tarayıcıda aç", "language": "Arayüz dilini seç (en/tr)",
    "config show": "Kalıcı kabuk ayarlarını göster", "config prompt": "Komut istemi metnini ayarla",
    "config language": "Arayüz dilini seç (en/tr)",
    "whoami": "Geçerli Windows kullanıcı adını göster",
    "hostname": "Bilgisayar adını göster",
    "disk": "Sürücü kapasitesi ve kullanımını göster",
    "ram": "Fiziksel bellek kullanımını göster",
    "cpu": "İşlemci bilgilerini ve kullanımını göster",
    "gpu": "Algılanan grafik bağdaştırıcılarını listele",
    "battery": "Pil durumunu göster",
    "top": "Canlı işlem izleyicisi (çıkmak için Q)",
    "env": "Ortam değişkenlerini hassas değerleri gizleyerek listele",
    "which": "PATH üzerindeki çalıştırılabilir dosyayı bul",
    "kill": "Kullanıcıya ait işlemi onayla ve sonlandır",
    "reboot-shell": "Windows'u yeniden başlatmadan CleyxOS'u yeniden başlat",
    "tree": "Klasör ağacını göster",
    "find": "Dosya veya klasör adlarını ara",
    "grep": "Dosyada metin ara",
    "head": "Dosyanın ilk satırlarını göster",
    "tail": "Dosyanın son satırlarını göster",
    "wc": "Satır, sözcük ve karakterleri say",
    "du": "Dosya veya klasör boyutunu hesapla",
    "df": "Dosya sistemi depolama bilgilerini göster",
    "hash": "Dosyanın SHA-256 özetini hesapla",
    "zip": "ZIP arşivi oluştur",
    "unzip": "ZIP arşivini güvenle aç",
    "edit": "Dosyayı sistem düzenleyicisinde aç",
    "backup": "Dosya veya klasörün ZIP yedeğini oluştur",
    "restore": "ZIP yedeğini güvenle geri yükle",
    "ip": "Yerel ağ arayüzlerini listele",
    "publicip": "HTTPS ile genel IP adresini getir",
    "dns": "A, AAAA, MX, TXT veya CNAME kaydı sorgula",
    "http": "HTTP yanıt bilgilerini incele",
    "download": "HTTPS üzerinden onaylı dosya indir",
    "netstat": "Ağ bağlantılarını ve işlem kimliklerini listele",
    "speedtest": "Onaylı yaklaşık bant genişliği testi yap",
    "todo": "Kalıcı görevleri yönet",
    "todo add": "Kalıcı görev ekle", "todo list": "Görevleri listele",
    "todo done": "Görevi tamamlandı olarak işaretle", "todo remove": "Görevi onayla ve sil",
    "todo clear": "Tüm görevleri onayla ve temizle",
    "note": "Kalıcı notları yönet", "note add": "Kalıcı not kaydet",
    "note list": "Notları listele", "note read": "Notu kimliğiyle oku",
    "note remove": "Notu onayla ve sil", "note search": "Notlarda ara",
    "timer": "Geri sayım sayacı başlat", "stopwatch": "Etkileşimli kronometre",
    "remind": "CleyxOS açıkken hatırlatıcı kur",
    "alias": "Güvenli komut kısayollarını yönet", "alias add": "Güvenli komut kısayolu ekle",
    "alias list": "Komut kısayollarını listele", "alias remove": "Komut kısayolunu kaldır",
    "matrix": "Animasyonlu Matrix yağmurunu göster (çıkmak için Q)",
    "cleyx": "CleyxOS sürüm ve platform bilgilerini göster",
}

_MESSAGES_TR = {
    "No matches found.": "Eşleşme bulunamadı.",
    "No matching notes.": "Eşleşen not bulunamadı.",
    "No records found.": "Kayıt bulunamadı.",
    "No graphics adapter information available.": "Grafik bağdaştırıcısı bilgisi bulunamadı.",
    "Cancelled.": "İptal edildi.",
    "Download cancelled.": "İndirme iptal edildi.",
    "Speed test cancelled.": "Hız testi iptal edildi.",
    "Extraction cancelled.": "Arşivden çıkarma iptal edildi.",
    "Deletion cancelled.": "Silme iptal edildi.",
    "Tasks cleared.": "Görevler temizlendi.",
    "Task removed.": "Görev kaldırıldı.",
    "Note removed.": "Not kaldırıldı.",
    "Aliases can target only safe documented CleyxOS commands or other aliases.": "Kısayollar yalnızca güvenli CleyxOS komutlarına veya diğer kısayollara yönlenebilir.",
    "Alias name conflicts with a built-in command.": "Kısayol adı yerleşik bir komutla çakışıyor.",
    "Alias cycle detected; remove or redefine the recursive alias.": "Kısayol döngüsü algılandı; özyinelemeli kısayolu kaldırın veya yeniden tanımlayın.",
    "Alias expansion limit reached; possible recursive alias.": "Kısayol genişletme sınırına ulaşıldı; özyinelemeli kısayol olabilir.",
    "Refusing to terminate a protected or CleyxOS process.": "Korunan veya CleyxOS işlem sonlandırılamaz.",
    "You may only terminate processes owned by your current user.": "Yalnızca geçerli kullanıcınıza ait işlemleri sonlandırabilirsiniz.",
    "Access denied while inspecting that process.": "İşlem incelenirken erişim reddedildi.",
    "Windows denied permission to terminate that process.": "Windows bu işlemi sonlandırma izni vermedi.",
    "Refusing a download redirected to a non-HTTPS URL.": "HTTPS olmayan bir adrese yönlendirilen indirme reddedildi.",
    "Downloaded files are never run automatically.": "İndirilen dosyalar hiçbir zaman otomatik çalıştırılmaz.",
    "Overwrite existing files?": "Mevcut dosyaların üzerine yazılsın mı?",
    "Remove all tasks?": "Tüm görevler kaldırılsın mı?",
    "Remove note": "Not kaldırılsın",
    "Terminate process": "İşlem sonlandırılsın",
    "Run a bandwidth test (about 6 MiB of traffic)?": "Bant genişliği testi çalıştırılsın mı (yaklaşık 6 MiB trafik)?",
    "Enter a valid domain name.": "Geçerli bir alan adı girin.",
    "Record type must be A, AAAA, MX, TXT, or CNAME.": "Kayıt türü A, AAAA, MX, TXT veya CNAME olmalıdır.",
    "Duration must look like 30s, 5m, 1h, or 1d.": "Süre 30s, 5m, 1h veya 1d biçiminde olmalıdır.",
    "Duration must be greater than zero and no longer than 7 days.": "Süre sıfırdan büyük ve 7 günden kısa olmalıdır.",
    "Task text cannot be empty.": "Görev metni boş olamaz.",
    "Note text cannot be empty.": "Not metni boş olamaz.",
    "Enter a valid HTTPS URL.": "Geçerli bir HTTPS adresi girin.",
    "Enter a valid HTTP or HTTPS URL.": "Geçerli bir HTTP veya HTTPS adresi girin.",
    "Credentials in URLs are not allowed.": "URL içinde kimlik bilgilerine izin verilmez.",
    "Download exceeds the 512 MiB safety limit.": "İndirme 512 MiB güvenlik sınırını aşıyor.",
    "Download exceeded the 512 MiB safety limit.": "İndirme 512 MiB güvenlik sınırını aştı.",
    "Archive contains too many entries (maximum 10,000).": "Arşiv çok fazla öğe içeriyor (en fazla 10.000).",
    "Archive exceeds the 2 GiB expanded-size safety limit.": "Arşivin açılmış boyutu 2 GiB güvenlik sınırını aşıyor.",
    "Archive contains duplicate or colliding paths.": "Arşiv yinelenen veya çakışan yollar içeriyor.",
    "Archive destination cannot be inside a directory being archived.": "Arşiv hedefi yedeklenen klasörün içinde olamaz.",
    "Archive filename must end in .zip.": "Arşiv dosya adı .zip ile bitmelidir.",
    "Backup destination must be a new .zip file.": "Yedek hedefi yeni bir .zip dosyası olmalıdır.",
    "Backup file is not a valid ZIP archive.": "Yedek dosyası geçerli bir ZIP arşivi değil.",
    "Provide at least one file or directory to archive.": "Arşivlemek için en az bir dosya veya klasör belirtin.",
    "Refresh interval must be 0.25–5 seconds.": "Yenileme aralığı 0,25–5 saniye olmalıdır.",
    "Sort order must be cpu, ram, or name.": "Sıralama cpu, ram veya name olmalıdır.",
    "Line count must be between 0 and 10000.": "Satır sayısı 0 ile 10000 arasında olmalıdır.",
    "ID must be a positive integer.": "Kimlik pozitif bir tam sayı olmalıdır.",
    "No battery information (desktop or unsupported device).": "Pil bilgisi yok (masaüstü veya desteklenmeyen cihaz).",
    "No matching application found.": "Eşleşen uygulama bulunamadı.",
    "Refine the application name and try again.": "Uygulama adını netleştirip yeniden deneyin.",
    "This application does not have a supported launch target.": "Bu uygulamanın desteklenen bir başlatma hedefi yok.",
    "Arguments are not supported for Start Menu shortcuts.": "Başlat menüsü kısayolları bağımsız değişken kabul etmez.",
    "Refusing to archive a symbolic link.": "Sembolik bağlantı arşivlenemez.",
    "Alias must be one CleyxOS command; shell chaining is not allowed.": "Kısayol tek bir CleyxOS komutu olmalıdır; kabuk zincirlemeye izin verilmez.",
    "An alias must be one CleyxOS command; shell chaining is not allowed.": "Kısayol tek bir CleyxOS komutu olmalıdır; kabuk zincirlemeye izin verilmez.",
    "Alias names must start with a letter and contain only letters, digits, '_' or '-'.": "Kısayol adı harfle başlamalı ve yalnızca harf, rakam, '_' veya '-' içermelidir.",
    "Use start, pause, resume, reset, time, or q.": "start, pause, resume, reset, time veya q kullanın.",
    "Shutting down CleyxOS. See you soon.": "CleyxOS kapatılıyor. Görüşmek üzere.",
    "[success]Directory created.[/success]": "[success]Klasör oluşturuldu.[/success]",
    "[success]File created (or already exists).[/success]": "[success]Dosya oluşturuldu (veya zaten mevcut).[/success]",
    "[success]Copied.[/success]": "[success]Kopyalandı.[/success]",
    "[success]Moved.[/success]": "[success]Taşındı.[/success]",
    "[success]Deleted.[/success]": "[success]Silindi.[/success]",
    "[warning]Deletion cancelled.[/warning]": "[warning]Silme iptal edildi.[/warning]",
    "[warning]Cancelled.[/warning]": "[warning]İptal edildi.[/warning]",
    "[warning]Download cancelled.[/warning]": "[warning]İndirme iptal edildi.[/warning]",
    "[warning]Speed test cancelled.[/warning]": "[warning]Hız testi iptal edildi.[/warning]",
    "[warning]Extraction cancelled.[/warning]": "[warning]Arşivden çıkarma iptal edildi.[/warning]",
    "[dim]No commands in history yet.[/dim]": "[dim]Henüz komut geçmişi yok.[/dim]",
    "Press Ctrl+C to cancel the timer.": "Sayacı iptal etmek için Ctrl+C tuşlarına basın.",
    "Run a bandwidth test (about 6 MiB of traffic)?": "Bant genişliği testi çalıştırılsın mı (yaklaşık 6 MiB trafik)?",
    "Enter a valid domain name.": "Geçerli bir alan adı girin.",
    "Record type must be A, AAAA, MX, TXT, or CNAME.": "Kayıt türü A, AAAA, MX, TXT veya CNAME olmalıdır.",
    "Duration must look like 30s, 5m, 1h, or 1d.": "Süre 30s, 5m, 1h veya 1d biçiminde olmalıdır.",
    "Duration must be greater than zero and no longer than 7 days.": "Süre sıfırdan büyük ve 7 günden kısa olmalıdır.",
    "Task text cannot be empty.": "Görev metni boş olamaz.",
    "Note text cannot be empty.": "Not metni boş olamaz.",
    "Enter a valid HTTPS URL.": "Geçerli bir HTTPS adresi girin.",
    "Enter a valid HTTP or HTTPS URL.": "Geçerli bir HTTP veya HTTPS adresi girin.",
    "Credentials in URLs are not allowed.": "URL içinde kimlik bilgilerine izin verilmez.",
    "Download exceeds the 512 MiB safety limit.": "İndirme 512 MiB güvenlik sınırını aşıyor.",
    "Download exceeded the 512 MiB safety limit.": "İndirme 512 MiB güvenlik sınırını aştı.",
    "Archive contains too many entries (maximum 10,000).": "Arşiv çok fazla öğe içeriyor (en fazla 10.000).",
    "Archive exceeds the 2 GiB expanded-size safety limit.": "Arşivin açılmış boyutu 2 GiB güvenlik sınırını aşıyor.",
    "Archive contains duplicate or colliding paths.": "Arşiv yinelenen veya çakışan yollar içeriyor.",
    "Archive destination cannot be inside a directory being archived.": "Arşiv hedefi yedeklenen klasörün içinde olamaz.",
    "Archive filename must end in .zip.": "Arşiv dosya adı .zip ile bitmelidir.",
    "Backup destination must be a new .zip file.": "Yedek hedefi yeni bir .zip dosyası olmalıdır.",
    "Backup file is not a valid ZIP archive.": "Yedek dosyası geçerli bir ZIP arşivi değil.",
    "Provide at least one file or directory to archive.": "Arşivlemek için en az bir dosya veya klasör belirtin.",
    "Refresh interval must be 0.25–5 seconds.": "Yenileme aralığı 0,25–5 saniye olmalıdır.",
    "Sort order must be cpu, ram, or name.": "Sıralama cpu, ram veya name olmalıdır.",
    "Line count must be between 0 and 10000.": "Satır sayısı 0 ile 10000 arasında olmalıdır.",
    "ID must be a positive integer.": "Kimlik pozitif bir tam sayı olmalıdır.",
    "No matches found.": "Eşleşme bulunamadı.",
    "No matching notes.": "Eşleşen not bulunamadı.",
    "No records found.": "Kayıt bulunamadı.",
    "No graphics adapter information available.": "Grafik bağdaştırıcısı bilgisi bulunamadı.",
    "No battery information (desktop or unsupported device).": "Pil bilgisi yok (masaüstü veya desteklenmeyen cihaz).",
    "No matching application found.": "Eşleşen uygulama bulunamadı.",
    "Refine the application name and try again.": "Uygulama adını netleştirip yeniden deneyin.",
    "This application does not have a supported launch target.": "Bu uygulamanın desteklenen bir başlatma hedefi yok.",
    "Arguments are not supported for Start Menu shortcuts.": "Başlat menüsü kısayolları bağımsız değişken kabul etmez.",
    "Refusing to archive a symbolic link.": "Sembolik bağlantı arşivlenemez.",
    "Alias names must start with a letter and contain only letters, digits, '_' or '-'.": "Kısayol adı harfle başlamalı ve yalnızca harf, rakam, '_' veya '-' içermelidir.",
    "Use start, pause, resume, reset, time, or q.": "start, pause, resume, reset, time veya q kullanın.",
    "Unknown command: ": "Bilinmeyen komut: ",
    "No matching notes.": "Eşleşen not bulunamadı.",
    "No records found.": "Kayıt bulunamadı.",
    "No matches found.": "Eşleşme bulunamadı.",
    "No matching application found for '": "' ile eşleşen uygulama bulunamadı.",
    "No item with ID ": "Bu kimlikte öğe yok: ",
    "Executable not found:": "Çalıştırılabilir dosya bulunamadı:",
    "Process ": "İşlem ",
    "Could not open the default browser.": "Varsayılan tarayıcı açılamadı.",
}

_USAGE_TR = {
    "whoami": "Kullanım: whoami", "hostname": "Kullanım: hostname", "disk": "Kullanım: disk",
    "ram": "Kullanım: ram", "cpu": "Kullanım: cpu", "gpu": "Kullanım: gpu",
    "battery": "Kullanım: battery", "top": "Kullanım: top [yenileme_saniyesi]",
    "env": "Kullanım: env", "which": "Kullanım: which <komut>", "kill": "Kullanım: kill <pid>",
    "reboot-shell": "Kullanım: reboot-shell", "tree": "Kullanım: tree [yol]",
    "find": "Kullanım: find <dosya_adı> [klasör]", "grep": "Kullanım: grep <metin> <dosya>",
    "head": "Kullanım: head <dosya> [satır_sayısı]", "tail": "Kullanım: tail <dosya> [satır_sayısı]",
    "wc": "Kullanım: wc <dosya>", "du": "Kullanım: du [yol]", "df": "Kullanım: df",
    "hash": "Kullanım: hash <dosya>", "zip": "Kullanım: zip <arşiv.zip> <dosyalar...>",
    "unzip": "Kullanım: unzip <arşiv.zip> [hedef]", "edit": "Kullanım: edit <dosya>",
    "backup": "Kullanım: backup <kaynak> <hedef.zip>", "restore": "Kullanım: restore <yedek.zip> <hedef>",
    "ip": "Kullanım: ip", "publicip": "Kullanım: publicip", "dns": "Kullanım: dns <alan_adı> [A|AAAA|MX|TXT|CNAME]",
    "http": "Kullanım: http <url>", "download": "Kullanım: download <https-url> [hedef]",
    "netstat": "Kullanım: netstat", "speedtest": "Kullanım: speedtest",
    "todo": "Kullanım: todo add <görev> | list | done <id> | remove <id> | clear",
    "note": "Kullanım: note add <metin> | list | read <id> | remove <id> | search <sorgu>",
    "timer": "Kullanım: timer <süre> (örnek: 30s, 5m, 1h)",
    "stopwatch": "Kullanım: stopwatch", "remind": "Kullanım: remind <süre> <mesaj>",
    "alias": "Kullanım: alias add <ad> <komut> | list | remove <ad>",
    "matrix": "Kullanım: matrix [hız 0.03–0.5 saniye]", "cleyx": "Kullanım: cleyx",
    "config": "Kullanım: config <show|prompt|language> [değer]",
    "app": "Kullanım: app <add|run|remove|info> ...",
}


def get_language() -> str:
    language = str(get_config().get("language", "en")).casefold()
    return language if language in SUPPORTED_LANGUAGES else "en"


def translate(key: str, **values: str) -> str:
    language = get_language()
    template = _TRANSLATIONS[language].get(key, _TRANSLATIONS["en"].get(key, key))
    return template.format(**values)


def command_description(command: str, fallback: str) -> str:
    return _DESCRIPTIONS_TR.get(command, fallback) if get_language() == "tr" else fallback


def translate_message(message: str) -> str:
    """Translate known command-facing messages while preserving user data."""
    if get_language() != "tr":
        return message
    if message.startswith("Usage: "):
        command = message[7:].split(maxsplit=1)[0].strip("<[").casefold()
        return _USAGE_TR.get(command, "Kullanım: " + message[7:])
    if message in _MESSAGES_TR:
        return _MESSAGES_TR[message]
    dynamic_patterns = (
        (r"Download (.+) to (.+)\? Downloaded files are never run automatically\.",
         lambda match: f"{match.group(1)} şu konuma indirilsin mi: {match.group(2)}? İndirilen dosyalar otomatik çalıştırılmaz."),
        (r"Terminate process (.+)\?", lambda match: f"{match.group(1)} işlemi sonlandırılsın mı?"),
        (r"Remove task #(\d+)\?", lambda match: f"#{match.group(1)} numaralı görev kaldırılsın mı?"),
        (r"Remove note #(\d+)\?", lambda match: f"#{match.group(1)} numaralı not kaldırılsın mı?"),
        (r"Overwrite existing files\?", lambda match: "Mevcut dosyaların üzerine yazılsın mı?"),
        (r"Terminate process (.+) \((\d+)\)\?", lambda match: f"{match.group(1)} işlemi (PID {match.group(2)}) sonlandırılsın mı?"),
        (r"Delete (.+)\? This cannot be undone\. Type 'yes' to confirm: ", lambda match: f"{match.group(1)} silinsin mi? Bu işlem geri alınamaz. Onaylamak için 'yes' yazın: "),
    )
    for pattern, render in dynamic_patterns:
        match = re.fullmatch(pattern, message)
        if match:
            return render(match)
    for english, turkish in _MESSAGES_TR.items():
        if message.startswith(english) and len(message) > len(english):
            return turkish + message[len(english):]
    match = re.fullmatch(r"Added task #(\d+)\.", message)
    if match:
        return f"#{match.group(1)} numaralı görev eklendi."
    match = re.fullmatch(r"Task #(\d+) completed\.", message)
    if match:
        return f"#{match.group(1)} numaralı görev tamamlandı."
    match = re.fullmatch(r"Added note #(\d+)\.", message)
    if match:
        return f"#{match.group(1)} numaralı not eklendi."
    match = re.fullmatch(r"Downloaded (.+) to (.+)\.", message)
    if match:
        return f"{match.group(1)} indirildi: {match.group(2)}."
    match = re.fullmatch(r"Backup created: (.+)", message)
    if match:
        return f"Yedek oluşturuldu: {match.group(1)}"
    match = re.fullmatch(r"\[success\]Added task #(\d+)\.\[/success\]", message)
    if match:
        return f"[success]#{match.group(1)} numaralı görev eklendi.[/success]"
    match = re.fullmatch(r"\[success\]Task #(\d+) completed\.\[/success\]", message)
    if match:
        return f"[success]#{match.group(1)} numaralı görev tamamlandı.[/success]"
    match = re.fullmatch(r"\[success\]Added note #(\d+)\.\[/success\]", message)
    if match:
        return f"[success]#{match.group(1)} numaralı not eklendi.[/success]"
    match = re.fullmatch(r"\[success\]Backup created: (.+)\[/success\]", message)
    if match:
        return f"[success]Yedek oluşturuldu: {match.group(1)}[/success]"
    match = re.fullmatch(r"\[success\]Downloaded (.+) to (.+)\.\[/success\]", message)
    if match:
        return f"[success]{match.group(1)} indirildi: {match.group(2)}.[/success]"
    match = re.fullmatch(r"\[success\]Alias '(.+)' (saved|removed)\.\[/success\]", message)
    if match:
        status = "kaydedildi" if match.group(2) == "saved" else "kaldırıldı"
        return f"[success]'{match.group(1)}' kısayolu {status}.[/success]"
    match = re.fullmatch(r"\[success\]Extracted (\d+) file\(s\) to (.+)\.\[/success\]", message)
    if match:
        return f"[success]{match.group(1)} dosya şuraya çıkarıldı: {match.group(2)}.[/success]"
    if message.startswith("Executable not found:"):
        return message.replace("Executable not found:", "Çalıştırılabilir dosya bulunamadı:")
    if message.startswith("No item with ID "):
        return message.replace("No item with ID ", "Bu kimlikte öğe yok: ")
    if message.startswith("Process ") and message.endswith(" does not exist."):
        return message.replace("Process ", "İşlem ").replace(" does not exist.", " mevcut değil.")
    if message.startswith("Terminate process "):
        return message.replace("Terminate process ", "İşlem sonlandırılsın ")
    if message.startswith("Remove task #"):
        return message.replace("Remove task #", "Görev kaldırılsın #")
    if message.startswith("Remove note #"):
        return message.replace("Remove note #", "Not kaldırılsın #")
    return message
