# Spectra

<div align="center">
  <img src="../img/logo.png" alt="Spectra Logo" width="200"/>
</div>

> **Yapay Zeka Destekli Reverse Engineering Aracısı** — IDA Pro, Binary Ninja, terminaliniz ve Android APK'lar için JADX içinde yaşayan akıllı bir asistan. [Rikugan](https://github.com/buzzer-re/Rikugan) projesinden fork edilmiştir.

[Documentation](docs/USAGE.md) | [Architecture](docs/ARCHITECTURE.md) | [Issues](https://github.com/alicangnll/Spectra/issues)

---

## Proje Genel Bakış

Spectra, **reverse engineering araçlarına gömülü bir yapay zeka aracısıdır**. IDA Pro ve Binary Ninja içinde, terminalinizde ve JADX üzerinden Android APK'larda doğrudan çalışan, birden fazla LLM sağlayıcısını destekleyen bir asistandır.

**Rikugan'dan Fork** — Spectra bu güçlü temel üzerine inşa edilmiştir ve şu iyileştirmeleri ekler:
- **240+ araç** (123 IDA Pro + 125 Binary Ninja)
- **63 yerleşik yetenek** (Rikugan'da 12)
- **4 platform** — IDA Pro, Binary Ninja, etkileşimli CLI, JADX
- **Gelişmiş güvenlik analizi** — Exploit, malware, firmware, mobil
- **Cihaz etkileşimi** — ADB (Android) + iOS cihaz araçları (libimobiledevice)
- **JADX entegrasyonu** — Android APK reverse engineering

---

## Spectra vs Rikugan

### Temel Farklar

| Özellik | Rikugan | Spectra |
|---------|---------|---------|
| **Yetenekler** | 12 yerleşik | 63 yerleşik |
| **Araçlar** | 60+ | 123 (IDA Pro) / 125 (Binary Ninja) |
| **Platformlar** | IDA, Binary Ninja | IDA, Binary Ninja, etkileşimli CLI, JADX |
| **Mobil Exploit** | ❌ | ✅ iOS/Android PAC/MTE bypass |
| **APK Analizi** | ❌ | ✅ Tam JADX entegrasyonu |
| **iOS Cihaz Araçları** | ❌ | ✅ libimobiledevice (eşleştirme, syslog, uygulamalar, çökme raporları, yedekler, SSH) |
| **Güvenlik Araçları** | Temel | Gelişmiş (Xref görselleştirici, akıllı adlandırma) |
| **Tip Kurtarma** | ❌ | ✅ Otomatik tespit |
| **Fonksiyon Navigasyonu** | ❌ | ✅ Tıklanabilir isimler/adresler |
| **Anti-Debug Tespiti** | ❌ | ✅ Otomatik |
| **API Vurgulama** | ❌ | ✅ MITRE ATT&CK etiketli |
| **LPE Tespiti** | ❌ | ✅ Yerel privilege escalation |
| **RCE Tespiti** | ❌ | ✅ Uzaktan kod çalıştırma |
| **OWASP Top 10** | ❌ | ✅ Mobil + Web |
| **Sürücü Exploit** | ❌ | ✅ Linux/macOS/Windows |
| **SSL Pinning** | ❌ | ✅ Yapısal tespit (içe aktarmalar/XREF'ler/pin malzemesi) + bypass kataloğu |
| **VM Obfuscation** | ❌ | ✅ Tespit |
| **MCP Sunucu Yönetimi** | ❌ | ✅ Ayarlar arayüzü + güvenlik doğrulayıcı |
| **Güvensiz Komut İzni** | ❌ | ✅ Tüm araç geçitleri için tek global anahtar |
| **GLM Desteği** | ❌ | ✅ GLM-4 & GLM-5 serisi |

### Miras Alınan Özellikler (Rikugan'dan)

- **Generator tabanlı aracı döngüsü** — Akıcı yanıtlar
- **Otomatik araç çalıştırma** — Manuel müdahale gerekmez
- **Keşif modu** — Paralel alt aracı orkestrasyonu
- **Doğal dil yamaları** — `/modify` ile doğal dil yamalama
- **Deobfuscation** — Binary Ninja IL dönüşümleri
- **MCP entegrasyonu** — Genişletilebilirlik

### Eklenen Özellikler (Spectra)

- **63 güvenlik yeteneği** — Exploit, malware, firmware, mobil
- **Etkileşimli CLI kabuğu** — RE araçları dışında kullanım (`spectra-cli`)
- **JADX CLI** — Android APK analizi
- **Xref Görselleştirici** — İnteraktif çağrı grafikleri
- **Akıllı Fonksiyon Adlandırma** — Yapay zeka destekli fonksiyon adlandırma
- **Tip Kütüphanesi Otomatik Tespit** — Otomatik tip kütüphanesi tespiti
- **Bulunanları Yer İmeleme** — Bulguları işaretle ve dışa aktar
- **Şüpheli API Vurgulama** — Tehlikeli API'leri vurgula
- **Anti-Debug Tespiti** — Otomatik anti-debug tespiti
- **Yapısal SSL Sabitleme Tespiti** — Sabitlemeyi ikilinin kendisinden bulur (içe aktarmalar, XREF'ler, yerel trust sembolleri, gömülü pin malzemesi); güven destekli kararlar ve hook/patch hedefleriyle
- **iOS Cihaz Araçları** — libimobiledevice tabanlı iPhone/iPad etkileşimi (eşleştirme, syslog, uygulama yönetimi, çökme raporları, yedekler, jailbreak'li cihazlarda SSH) — ADB'nin iOS karşılığı
- **Güvensiz Komut İzni** — Tek bir Ayarlar anahtarı tüm araç düzeyi güvenlik geçitlerini atlar (ADB/iOS güvenli listeleri, betik koruması, ağ onayları)
- **MCP Sunucu Yönetimi** — Ayarlar'dan MCP sunucuları ekle/kaldır; yol ve argüman güvenlik doğrulamasıyla
- **Güvenli Otomatik Güncelleyici** — SHA-256 sağlama toplamı doğrulanmış güncelleme paketleri, açılışta güncelleme kontrolü, kurulum sonrası veritabanını kaydet & uygulamayı yeniden başlat
- **Windows otomatik kurulum** — Otomatik bağımlılık kurulumu

---

### Önerilen Sağlayıcılar

| Sağlayıcı | Kalite | Notlar |
|----------|---------|-------|
| **Claude Opus 4.6** | ⭐⭐⭐⭐⭐ | Genel en iyi, prompt caching |
| **Claude Sonnet 4.6** | ⭐⭐⭐⭐ | Düşük maliyet, güçlü |
| **GLM-5.2** | ⭐⭐⭐⭐⭐ | Amiral gemisi, 1M context, agent engineering |
| **GLM-5** | ⭐⭐⭐⭐⭐ | Güçlü kodlama, karmaşık sistemler |
| **GLM-5-Turbo** | ⭐⭐⭐⭐ | Hızlı, agent optimize edilmiş |
| **GLM-4-Plus** | ⭐⭐⭐⭐ | Güvenilir, ¥5/M (~$0.70) |
| **GLM-4.7-Flash** | ⭐⭐⭐⭐ | Ultra ucuz, $0.06/M input |
| **MiniMax M2.5** | ⭐⭐⭐⭐ | Cömert limitler, düşük maliyet |
| **Gemini 3.1 Pro** | ⭐⭐⭐ | İyi, daha fazla halüsinasyon |
| **Ollama (Yerel)** | ⭐⭐⭐ | Çevrimdışı, modele bağlı |

---

## Platform Desteği

| Platform | Durum | Notlar |
|----------|--------|-------|
| **IDA Pro 9.0+** | ✅ Full | Hex-Rays decompiler gerektirir |
| **Binary Ninja 3164+** | ✅ Full | UI modu |
| **Terminal (CLI)** | ✅ Full | `spectra-cli` interaktif kabuk |
| **JADX** | ✅ Full | APK analizi CLI |
| **VSCode** | 🚧 Planlandı | Uzantı henüz yayınlanmadı — Yol Haritası'na bakın |

---

## Kurulum

### Kurulum

**Kurulu platformları otomatik tespit eder:**

```bash
# Linux / macOS
curl -fsSL https://raw.githubusercontent.com/alicangnll/Spectra/main/install.sh | bash

# Windows (PowerShell)
irm https://raw.githubusercontent.com/alicangnll/Spectra/main/install.ps1 | iex
```

Kurulum betiği ayrıca **iOS cihaz araçlarını** da kurar (macOS'ta Homebrew ile, Linux'ta apt/dnf/pacman/zypper ile libimobiledevice + usbmuxd); böylece `ios_*` araçları kutudan çıktığı gibi çalışır. Atlamak için: `--no-ios`.

---

### Manuel IDA Python Yapılandırması (Linux / macOS)

> [!NOTE]
> Installer bu adımları otomatik olarak gerçekleştirir. Bu bölümü yalnızca otomatik kurulum başarısız olursa veya IDA'nın Python'unu manuel olarak yeniden yapılandırmanız gerekirse takip edin.

#### Neden Gerekli?

IDA Pro **kendi gömülü Python yorumlayıcısını** içerir — varsayılan olarak sistem `python3`'ünü kullanmaz.
`pip3` ile kurulan paketler sistem Python'unun site-packages dizinine gider; IDA bunu göremez.
Çözüm: IDA'yı ve `pip`'i **aynı Python versiyonunu** kullanacak şekilde yapılandırmak.

#### Adım 1 — Sistemdeki Python Versiyonunu Kontrol Et

```bash
python3 --version
# Örnek çıktı: Python 3.13.0
```

#### Adım 2 — `idapyswitch` ile Eşleşen Versiyonu Seç

```bash
cd ~/ida-pro-9.1   # IDA kurulum dizinini ayarlayın
./idapyswitch
```

Örnek çıktı:
```
The following Python installations were found:
    #0: 3.14.0 ('3.14') (/usr/lib/x86_64-linux-gnu/libpython3.14.so.1.0)
    #1: 3.13.0 ('3.13') (/usr/lib/x86_64-linux-gnu/libpython3.13.so.1.0)
Please pick a number between 0 and 1 (default: 0)
```

Sistem `python3` versiyonunuzla eşleşen numarayı girin (örn. 3.13 için `1`).

> [!IMPORTANT]
> Her zaman sistem `python3` / `pip3` versiyonuyla eşleşen seçeneği seçin. Versiyon uyumsuzluğu (örn. IDA 3.14, pip 3.13) IDA içinde "module not found" hatasının en yaygın nedenidir.

#### Adım 3 — `anthropic`'i O Python Versiyonu İçin Kur

```bash
# Seçilen Python versiyonu için kur (örn. 3.13)
python3 -m pip install --user anthropic>=0.39.0

# Kurulduğunu doğrula
python3 -c "import anthropic; print(anthropic.__version__)"
```

#### Adım 4 — IDA İçinde Doğrula

IDA Pro'yu yeniden başlatın ve Python konsolunu açın:
```python
import anthropic

print(anthropic.__version__)  # kurulu versiyonu yazdırmalı
```

Hâlâ başarısız olursa IDA'nın Python'unun hangi site-packages dizinini kullandığını kontrol edin:
```python
import sys

for p in sys.path:
    print(p)
```
`~/.local/lib/pythonX.Y/site-packages` listede görünüyor mu kontrol edin.

#### Alternatif: `IDADIR` ile Zorla

Belirli bir IDA dizinini kullanmak için installer'ı şu şekilde çalıştırabilirsiniz:
```bash
IDADIR=/path/to/ida-pro-9.1 ./install_ida.sh
```

---

## Özellikler


### 🤖 Aracı Döngüsü (Rikugan'dan Miras Alınmış)

Akıcı yanıtlar için **generator tabanlı dönüş döngüsü**:
- Gerçek zamanlı token akışı — Yapay zekanın düşünüşünü görün
- Otomatik araç çalıştırma — Manuel müdahale gerekmez
- Hata kurtarma — Hatalardan otomatik kurtarma
- Plan modu — Çok adımlı iş akışları için onay sistemi
- Mesaj kuyruğu — Aracı çalışırken takip mesajları gönderin

### 🖥️ CLI Shell Arayüzü (Spectra v1.3+)

**Claude benzeri interaktif shell** terminal tabanlı analiz için:
```bash
python spectra_cli.py dir_loc /hedef/yolu
```

**Özellikler:**
- **63 yerleşik yetenek** — CLI'dan tüm güvenlik yeteneklerine erişim
- **Ajan araç seti** — Dosya işlemleri, shell komutları, kod analizi
- **SSH entegrasyonu** — Uzaktan komut yürütme, dosya transferi (SCP)
- **Oturum yönetimi** — Analiz oturumlarını kaydet/yükle
- **Plan/Araştırma modları** — Yapılandırılmış analiz iş akışları
- **Daralt/Genişlet** — **Ctrl+O** ile araç çıktısını değiştir
- **AI'ı Durdur** — Aracıyı durdurmak ve girdi istemine dönmek için **Ctrl+C**
- **Tab tamamlama** — Komutları, yetenekleri ve dosya yollarını otomatik tamamla
- **Komut geçmişi** — Kalıcı readline geçmişi (yukarı/aşağı oklar, Ctrl+R)
- **Çok satırlı girdi** — Girdiyi sonraki satıra devam etmek için `\` kullan
- **Markdown render** — Tablolar, kod blokları, sözdizimi vurgulama
- **Renkli çıktı** — Renk kodlu olaylarla sözdizimi vurgulu sonuçlar
- **Shell kaçışı** — `!komut` ile shell komutlarını çalıştır
- **Araç onayı** — Sözdizimi vurgulu önizlemelerle güvenli yürütme
- **Uzatılmış timeout** — Büyük kod tabanı analizi için 2 saat timeout (Linux kernel, vb.)
- **Config komutları** — `/config_edit` ile config dosyasını düzenle, `/apiurl` ile API URL set et
- **LM Studio desteği** — `/provider lmstudio` ile yerel modelleri kullan

**Kullanım:**
```bash
spectra> /kernel-exploit        # Kernel exploitation yeteneğini etkinleştir
spectra> /vuln-audit            # Güvenlik açığı değerlendirmesi
spectra> /plan Binary'i analiz et  # Yapılandırılmış analiz için plan modu
spectra> /save analiz-im        # Oturumu kaydet
spectra> /sessions              # Kayıtlı oturumları listele
spectra> /provider lmstudio     # LM Studio kullan (yerel LLM)
spectra> /apiurl http://localhost:1234/v1  # API URL set et
spectra> /config_edit           # Config'i editörde aç
```

**Desteklenen Sağlayıcılar:**
- `anthropic` — Claude API (Opus, Sonnet, Haiku)
- `openai` — OpenAI API (GPT-4, GPT-3.5)
- `gemini` — Google Gemini
- `ollama` — Yerel Ollama
- `glm` — Zhipu AI (GLM-4, GLM-5)
- `lmstudio` — LM Studio (yerel modeller)

### 🛠️ 240+ Araç

**IDA Pro (123 araç):**
- Navigasyon, decompilation, disassembly
- Cross-references, strings, imports, exports
- Annotations (rename, comment, set type)
- Microcode manipulation (Hex-Rays IL)
- Cihaz etkileşimi — ADB (Android) + iOS (libimobiledevice)
- Onaylı Python scripting

**Binary Ninja (125 araç):**
- Navigasyon, decompilation, HLIL
- Cross-references, strings, veritabanı sorguları
- IL okuma/yazma/dönüştürme
- Cihaz etkileşimi — ADB (Android) + iOS (libimobiledevice)
- Onaylı Python scripting

### 📚 63 Yerleşik Yetenek

**Exploit & Güvenlik:**
- `memory-corruption` — UAF, OOB, PAC, ASLR, CFI, CET, MTE bypass
- `kernel-exploit` — SMEP/SMAP/KPTI bypass
- `rop-builder` — Otomatik ROP zinciri oluşturma
- `race-condition` — TOCTOU exploitation
- `auto-exploit` — Otomatik exploit oluşturma
- `android-exploit` — Mobil exploitation teknikleri
- `ios-exploit` — ARM64 PAC bypass
- `lpe-detection` — Yerel privilege escalation
- `rce-detection` — Uzaktan kod çalıştırma

**Malware & Firmware:**
- `malware-analysis` — Sınıflandırma, C2, config çıkarma
- `linux-malware` — Linux malware analizi
- `mobile-malware-analysis` — Mobil malware
- `firmware-re` — Çıkarma ve analiz

**Analiz & Denetim:**
- `vuln-audit` — Güvenlik açığı değerlendirmesi
- `reverse-engineering` — Binary analiz
- `protocol-analysis` — Ağ protokolü RE
- `crypto-analysis` — Kriptografik algoritmalar
- `deobfuscation` — Control flow flattening kaldırma (Binary Ninja)

**Mobil & Web:**
- `jadx-analysis` — Android APK analizi
- `mobile-pentest` — Mobil uygulama değerlendirmesi
- `owasp-mobile-top10` — OWASP Mobil Top 10
- `owasp-web-top10` — OWASP Web Top 10
- `ssl-pinning-bypass` — SSL pinning bypass
- `app-shielding-bypass` — Uygulama koruması bypass

**Yamalama & Değiştirme:**
- `modify` — Doğal dil binary patch'leri
- `smart-patch-ida` — IDA patching iş akışı
- `smart-patch-binja` — Binary Ninja patching
- `shellcode-generator` — Payload oluşturma

**CTF & Araçlar:**
- `ctf` — CTF yarışma araçları
- `ida-scripting` — IDAPython API referansı
- `binja-scripting` — Binary Ninja Python API

### 🚀 Gelişmiş Güvenlik Araçları (v1.2.5+)

**Cross-Reference Görselleştirici**
- Karmaşıklık metrikleri ile interaktif çağrı grafikleri
- Fonksiyonlar arası yol bulma
- Bağımlılık analizi

**Akıllı Fonksiyon Adlandırma**
- Yapay zeka destekli desen tanıma
- `sub_XXX` fonksiyonları için anlamlı isimler önerir
- Davranış analizi temelinde

**Tip Kütüphanesi Otomatik Tespit**
- Platformu otomatik tespit eder (Windows/Linux)
- Tip kütüphanelerinden yapı tanımlarını kurtarır

**Bulunanları Yer İmeleme**
- Kategorilerle konumları işaretle (Kritik, Şüpheli, Doğrulanmış, vb.)
- Bulguları markdown raporu olarak dışa aktar
- Oturumlar arasında kalıcı

**Şüpheli API Vurgulama**
- MITRE ATT&CK referanslı renk kodlu tehlikeli API'ler
- [CRIT] CreateRemoteThread, WriteProcessMemory, VirtualAllocEx
- [HIGH] VirtualProtect, GetProcAddress, LoadLibrary
- [MED] InternetConnect, socket, CryptEncrypt

**Anti-Debugging Tespiti**
- Windows API kontrolleri (IsDebuggerPresent, CheckRemoteDebuggerPresent)
- PEB BeingDebugged erişim desenleri
- Assembly instructions (rdtsc, int 2d, int 3)

**Hex Adres Navigasyonu**
- Tüm hex adresler tıklanabilir olur (0x401000, 00401000, 401000h)
- Disassembly görünümünde konuma atla

**Fonksiyon İsmi Navigasyonu**
- CamelCase fonksiyonlar (generatePWFOTP) otomatik bağlanır
- snake_case fonksiyonlar (verify_password) bağlanır
- Akıllı eşleştirme yaygın anahtar kelimeleri atlar

### 📱 JADX Entegrasyonu (Spectra'ya Özel)

**Android APK Analizi:**
```bash
# APK yapısını analiz et
python spectra_jadx.py analyze app.apk -o ./decompiled

# String ara
python spectra_jadx.py search app.apk "API_KEY"

# Belirli bir sınıfı analiz et
python spectra_jadx.py class app.apk com.example.MainActivity

# Interaktif yapay zeka modu
python spectra_jadx.py interactive app.apk
```

**Özellikler:**
- Java kaynağına otomatik decompilation
- Manifest ayrıştırma (izinler, bileşenler, SDK)
- API anahtarları ve endpoint'ler için string arama
- Native kütüphane tespiti (.so dosyaları)
- Güvenlik değerlendirmesi

---

### Erişim

| Platform | Kısayol | Menü Konumu |
|----------|---------|--------------|
| **IDA Pro** | `Ctrl+Shift+I` | Edit → Plugins → Spectra |
| **Binary Ninja** | `Ctrl+Shift+I` | Tools → Spectra → Open Chat |
| **VSCode** | `Ctrl+Shift+I` | Command Palette → "Spectra: Open Chat" |

### API Anahtarı Yapılandırması

```bash
# Claude (Önerilen)
export ANTHROPIC_API_KEY="sk-ant-..."

# OpenAI uyumlu
export OPENAI_API_KEY="sk-..."

# Ollama (Yerel)
export OLLAMA_BASE_URL="http://localhost:11434"
```

---

## Gereksinimler

- **Python 3.10+**
- **IDA Pro 9.0+** Hex-Rays ile **VEYA** **Binary Ninja**
- **En az bir LLM sağlayıcısı**
- **Windows, macOS veya Linux**

---

## Windows ARM64 Desteği

Windows ARM64 kullanıyorsanız (örneğin Surface Pro X), IDA Pro x64 emülasyonu altında çalışır.

**Otomatik Çözüm (v1.2.5+):**
```cmd
# Spectra eksik bağımlılıkları otomatik tespit eder ve yükler
# Sadece IDA'yı başlatın — şunu göreceksiniz:
[Spectra] Attempting auto-install...
[Spectra] anthropic installed successfully
```

Otomatik kurulum başarısız olursa, bkz. [docs/WINDOWS_ARM64_FIX.md](docs/WINDOWS_ARM64_FIX.md).

---

## Kullanım Örnekleri

### Temel Analiz

```
User: Bu binary'yi analiz et ve ana işlevselliği bul
Spectra: [Binary'yi keşfeder, import/export'ları eşler, ana fonksiyonları analiz eder]

User: 0x401000 adresindeki fonksiyon ne yapıyor?
Spectra: [Fonksiyonu decompiles eder, mantığı açıklar, algoritmaları tanımlar]
```

### Güvenlik Açığı Avı

```
User: /skill memory-corruption
Spectra: [Yeteneği etkinleştirir, exploit tekniklerini yükler]

User: OOB güvenlik açıkları bul ve RCE exploit oluştur
Spectra: [Tehlikeli fonksiyonları tarar, bug bulur, zincir oluşturur]
```

### Mobil Exploitation

```
User: /skill ios-exploit
Spectra: [iOS exploitation yeteneğini etkinleştirir]

User: Bu binary'yi PAC bypass fırsatları için analiz et
Spectra: [Pointer authentication violations tarar]
Spectra: [PAC oracle gadget'lerini ve bypass stratejilerini tanımlar]
```

### APK Analizi

```
User: /jadx Bu APK'yi analiz et
Spectra: [APK'yi JADX ile decompiles eder]
Spectra: [Manifest çıkarır: izinler, aktiviteler, servisler]

User: C2 sunucu adresini bul
Spectra: [Decompiled kaynaklarda http:// desenlerini arar]
Spectra: [Bulundu: hxxp://c2.example.com/api]
```

### Kernel Exploitation

```
User: /skill kernel-exploit
Spectra: [Kernel exploitation yeteneğini etkinleştirir]

User: SMEP/SMAP bypass kontrolü yap
Spectra: [CR4 manipulation gadget'lerini tarar]
Spectra: [Olası bypass tekniklerini tanımlar]
```

---

## Sorun Giderme

**Eklenti görünmüyorsa:**
```bash
spectra-doctor --check-install
spectra-install --force
```

**API bağlantı sorunları:**
```bash
curl https://api.anthropic.com/v1/messages -H "x-api-key: $ANTHROPIC_API_KEY"
echo $HTTP_PROXY
```

**Performans sorunları:**
```bash
rm -rf ~/.spectra/cache/*
export SPECTRA_DEFAULT_MODEL="claude-sonnet-4-6"
```

---

## Geliştirme

Kurulum talimatları için bkz. [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

```bash
./ci-local.sh
python3 -m pytest tests/ -v
```

---

## Yol Haritası

**v1.3.x (Kısa vadeli):**
- [ ] Deobfuscation için ML tabanlı desen tanıma
- [ ] Otomatik exploit oluşturma için sembolik execution
- [ ] Gelişmiş kernel analiz yetenekleri

**v1.4.x (Orta vadeli):**
- [ ] Çoklu binary analiz iş akışı
- [ ] İşbirlikçi analiz özellikleri
- [ ] Ghidra, Radare2 entegrasyonu

---

## Katkıda Bulunma

Katkılar kabul edilir! Bkz. [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) ve [docs/AGENTS.md](docs/AGENTS.md).

---

## Teşekkürler

- **Claude Code** — Muazzam pair programmer
- **Anthropic** — İnanılmaz yapay zeka modelleri
- **Binary Ninja Ekibi** — Mükemmel API ve destek
- **Hex-Rays** — IDA Pro ve Hex-Rays decompiler
- **Topluluk** — Geri bildirim, test, katkılar

---

## Lisans

MIT License — bkz. [LICENSE](LICENSE) dosyası.

---

## Sorumluluk Reddi ve Kullanım Şartları

⚠️ **YASAL UYARI VE KULLANIM ŞARTLARI**

Spectra'yı kullanarak aşağı şartları kabul etmiş olursunuz:

### 1. Sadece Eğitim ve Araştırma Amaçlı

Spectra **SADECE** aşağıdaki amaçlar için tasarlanmıştır:
• Yetkili güvenlik testi ve penetrasyon testi
• Eğitim araştırması ve akademik çalışma
• Güvenlik açığı disclosure programları (bug bounty)
• CTF (Capture The Flag) yarışmaları
• Sahibi olduğunuz veya AÇIK izniniz olan sistemlerin analizi

### 2. Yasaklanmış Kullanımlar

Spectra'nın aşağıdaki amaçlarla kullanılması **KATİ YASAKTIR**:
• İzinsiz olarak bilgisayar sistemlerine erişim (izin olmadan hacking)
• Sahibi olmadığınız veya izniniz olmadığı sistemlere siber saldırılar
• Yerel, eyalet, federal veya uluslararası hukuk altında herhangi bir yasa dışı faaliyet
• Herhangi bir platform veya hizmetin kullanım şartlarını ihlal
• Taciz, takip veya başka bir kötü amaçlı faaliyet

### 3. Kullanıcı Sorumluluğu

Spectra'yı kullanarak şunları kabul etmiş olursunuz:
• Tüm eylemlerden SİZ sorumlusunuz
• Herhangi bir sistemi analiz etmeden önce yetkinizi doğrulamanız GEREKLİDİR
• Tüm geçerli yasalara ve yönetmeliklere uymanız GEREKLİDİR
• Spectra'nın yazarları, katkıda bulunanlar ve bakımcıları bu araçla
  işlenen herhangi bir kötüye kullanım, hasar, yasal sonuçlar veya yasa dışı
  faaliyetlerden sorumlu değildir

### 4. Yargı Yetkisi ve Uygunluk

Yasalar yargı bölgesine göre değişir. Sizin sorumluluğunuz:
• Bulunduğunuz yerdeki yasaları anlamak ve uymak
• Güvenlik testinden önce gerekli izinleri almak
• Bulunan güvenlik açıkları için sorumlu disclosure uygulamalarını takip etmek

İlgili yasalar şunları içerebilir (ancak bunlarla sınırlı değildir):
• Bilgisayar Suçları ve Kötüye Kullanım Yasası (ABD) / CFAA
• Bilgisayar Kötüye Kullanım Yasası (İngiltere)
• GDPR, CCPA ve veri koruma yasaları
• Yerel siber güvenlik ve hacking yasaları
• Uluslararası anlaşmalar ve sözleşmeler

### 5. Garanti Yok

Spectra herhangi bir garanti olmadan "OLDUĞU GİBİ" sağlanır. Yazarlar ve
katkıda bulunanlar, zımni garanti dahil ancak bununla sınırlı olmaksızın,
ticari kullanılabilirlik, belirli bir amaca uygunluk ve ihlal olmadığı
garantileri dahil ancak bunlarla sınırlı olmaksızın tüm garantileri reddederler.

### 6. Tazmin Edilme

Spectra'yı kullanarak, yazarları, katkıda bulunanları ve bakımcıları bu
yazılımın kullanımından veya kötüye kullanımından kaynaklanan talepler,
hasarlar, kayıplar, sorumluluklar, yasal ücretler ve giderlerden tazmin
etmeyi kabul etmiş olursunuz.

### 7. Yaş ve Rıza

Bu yazılımı kullanmak için yargı bölgenizde yasal yaşta olmanız GEREKLİDİR.
Spectra'yı kullanarak, bu şartları kabul etmek için yasal yetkiye sahip
olduğunuzu temsil edersiniz.

---

**Eğer bu şartları kabul etmiyorsanız, bu yazılımı KULLANMAYIN.**

---

**Şevk ile yapıldı — [Ali Can Gönüllü](https://github.com/alicangnll)**

*"Reverse engineering'in geleceği otomatik, akıllı ve herkes için erişilebilir."*
