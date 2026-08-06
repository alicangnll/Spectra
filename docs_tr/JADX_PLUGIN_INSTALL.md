# Spectra JADX Eklenti Kurulum Rehberi

Spectra'nın 4 farklı modda çalışan hibrit JADX eklenti sistemi için tam kurulum rehberi.

## İçindekiler

1. [Hızlı Başlangıç](#hızlı-başlangıç)
2. [Kurulum Modları](#kurulum-modları)
3. [Platforma Özgü Kurulum](#platforma-özgü-kurulum)
4. [Yapılandırma](#yapılandırma)
5. [Doğrulama](#doğrulama)
6. [Sorun Giderme](#sorun-giderme)

## Hızlı Başlangıç

### Otomatik Kurulum (Önerilen)

```bash
# Spectra'yı klonlayın veya indirin
cd /path/to/Spectra

# Evrensel kurulumu çalıştırın
python install_jadx_plugin.py
```

**Bu işlem şunları yapar:**
- Yüklü platformları algılar (JADX, IDA Pro, Binary Ninja)
- Spectra'yı JADX yerel eklentisi olarak yükler
- IDA/Binary Ninja ile entegrasyonu etkinleştirir (varsa)
- Yapılandırma dosyalarını ayarlar
- Python bağımlılıklarını yükler
- Başlatıcı komut dosyaları oluşturur

**Alternatif tek satırlık komut:**
```bash
curl -fsSL https://raw.githubusercontent.com/alicangnll/Spectra/main/install_jadx_plugin.py | python3
```

## Kurulum Modları

### Mod 1: JADX Yerel Eklenti

**En iyi için:** Günlük APK analiz iş akışı, JADX GUI kullanıcıları

#### Ön Koşullar
- JADX 1.4.7+ yüklü
- Python 3.10+
- 50MB boş disk alanı

#### Kurulum Adımları

**macOS:**
```bash
# JADX yükleyin
brew install jadx

# Kurulumu doğrulayın
jadx --version

# Spectra eklentisini yükleyin
cd /path/to/Spectra
python install_jadx_plugin.py

# Eklenti kurulumunu doğrulayın
ls -la ~/.jadx/plugins/spectra/
```

**Linux:**
```bash
# JADX yükleyin
wget https://github.com/skylot/jadx/releases/download/v1.4.7/jadx-1.4.7.zip
unzip jadx-1.4.7.zip
cd jadx-1.4.7
sudo ln -s $(pwd)/bin/jadx /usr/local/bin/jadx

# Doğrulayın
jadx --version

# Spectra eklentisini yükleyin
cd /path/to/Spectra
python install_jadx_plugin.py
```

**Windows:**
```powershell
# JADX'ı https://github.com/skylot/jadx/releases adresinden indirin
# C:\jadx konumuna çıkarın

# PATH'e ekleyin
setx PATH "%PATH%;C:\jadx\bin"

# Spectra eklentisini yükleyin
cd C:\path\to\Spectra
python install_jadx_plugin.py
```

#### Doğrulama
```bash
# Eklentinin yüklü olduğunu kontrol edin
python spectra_jadx.py plugin-info

# Şunu göstermeli:
# Environment: JADX
# Spectra available: True
```

#### Kullanım
```bash
# JADX GUI'den
Tools → Spectra → Analyze APK

# JADX CLI'den
jadx --plugin spectra app.apk -d output

# Doğrudan eklenti çağrısı
python ~/.jadx/plugins/spectra/spectra_jadx.py analyze app.apk -o output
```

### Mod 2: Bağımsız CLI Aracı

**En iyi için:** Toplu işleme, CI/CD, komut dosyası oluşturma, hızlı analiz

#### Kurulum

```bash
cd /path/to/Spectra

# Yürütülebilir yapın
chmod +x spectra_jadx.py

# PATH'e kopyalayın (isteğe bağlı)
sudo cp spectra_jadx.py /usr/local/bin/spectra-jadx
# Veya
cp spectra_jadx.py ~/.local/bin/spectra-jadx
```

#### Kullanım
```bash
# Doğrudan yürütme
python spectra_jadx.py analyze app.apk -o ./decompiled

# PATH'ten
spectra-jadx analyze app.apk -o ./decompiled

# Tüm komutlar
spectra-jadx analyze app.apk -o ./decompiled
spectra-jadx search app.apk "API_KEY"
spectra-jadx structure app.apk
spectra-jadx class app.apk com.example.MainActivity
spectra-jadx interactive app.apk
```

### Mod 3: IDA Pro Entegrasyonu

**En iyi için:** Derin tersine mühendislik, APK analizini ikili analizle birleştirme

#### Ön Koşullar
- IDA Pro 7.5+ yüklü
- IDA için Spectra eklentisi yüklü
- JADX yüklü (derleme için)

#### Kurulum

```bash
# Spectra zaten IDA Pro'ya yüklenmiş olmalı
# JADX entegrasyonu /jadx yeteneği üzerinden otomatiktir

# IDA Pro'da doğrulayın:
# 1. IDA Pro'yu açın
# 2. Ctrl+Shift+I tuşlarına basarak Spectra'yı açın
# 3. Şunu yazın: /jadx Analyze this APK at /path/to/app.apk
```

#### IDA Pro'da Kullanım

```
# Spectra sohbet panelinde (Ctrl+Shift+I):

# APK analiz et
/jadx Analyze this APK at /path/to/malware.apk

# Güvenlik değerlendirmesi
/jadx What permissions does this app request?
/jadx Find suspicious permissions

# Derin analiz
/jadx Check for hardcoded API keys
/jadx Analyze network communication
/jadx Find native libraries and their architectures
```

### Mod 4: Binary Ninja Entegrasyonu

**En iyi için:** Modern ikili analiz, çapraz platform uyumluluğu, API analizi

#### Ön Koşullar
- Binary Ninja 3.4+ yüklü
- Binary Ninja için Spectra eklentisi yüklü
- JADX yüklü (derleme için)

#### Kurulum

```bash
# Spectra zaten Binary Ninja'ya yüklenmiş olmalı
# JADX entegrasyonu /jadx yeteneği üzerinden otomatiktir

# Binary Ninja'da doğrulayın:
# 1. Binary Ninja'yı açın
# 2. Tools → Spectra → Open Chat
# 3. Şunu yazın: /jadx Analyze this APK at /path/to/app.apk
```

#### Binary Ninja'da Kullanım

```
# Spectra sohbet panelinde (Ctrl+Shift+I):

# APK analiz et
/jadx Analyze this APK at /path/to/app.apk

# Etkileşimli keşif
/jadx What are the main entry points?
/jadx Show me the manifest permissions
/jadx Find all exported activities
```

## Platforma Özgü Kurulum

### macOS

```bash
# Bağımlılıkları yükleyin
brew install jadx python3

# Spectra eklentisini yükleyin
cd /path/to/Spectra
python install_jadx_plugin.py

# PATH'e ekleyin (isteğe bağlı)
echo 'export PATH="$PATH:~/.local/bin"' >> ~/.zshrc
source ~/.zshrc
```

### Linux

```bash
# Bağımlılıkları yükleyin
sudo apt-get install python3 python3-pip

# JADX yükleyin
wget https://github.com/skylot/jadx/releases/download/v1.4.7/jadx-1.4.7.zip
unzip jadx-1.4.7.zip
sudo ln -s $(pwd)/jadx-1.4.7/bin/jadx /usr/local/bin/jadx

# Spectra eklentisini yükleyin
cd /path/to/Spectra
python install_jadx_plugin.py
```

### Windows

```powershell
# Python 3.10+ yükleyin (python.org adresinden)

# JADX yükleyin
# https://github.com/skylot/jadx/releases adresinden indirin
# C:\jadx konumuna çıkarın
# C:\jadx\bin konumunu sistem PATH'ine ekleyin

# Spectra eklentisini yükleyin
cd C:\path\to\Spectra
python install_jadx_plugin.py
```

## Yapılandırma

### Eklenti Yapılandırma Dosyası

**Konum:** `~/.jadx/plugins/spectra/config.json`

**Varsayılan Yapılandırma:**
```json
{
  "auto_analyze": true,
  "ai_provider": "anthropic",
  "api_key": "",
  "max_tokens": 8192,
  "model": "claude-sonnet-4-20250514",
  "temperature": 0.2,
  "security_checks": {
    "permissions": true,
    "hardcoded_secrets": true,
    "network_security": true,
    "native_libraries": true,
    "debuggable_check": true,
    "backup_check": true,
    "exported_components": true,
    "certificate_validation": true
  },
  "output_formats": {
    "json": true,
    "markdown": true,
    "xml": false,
    "html": false
  },
  "analysis_options": {
    "decompile_debug": false,
    "show_bad_code": true,
    "export_resources": true,
    "timeout_seconds": 300
  }
}
```

### Ortam Değişkenleri

```bash
# AI sağlayıcısını ayarlayın
export SPECTRA_AI_PROVIDER="anthropic"  # veya "openai", "local"

# API anahtarını ayarlayın
export SPECTRA_API_KEY="your-api-key"

# Modeli ayarlayın
export SPECTRA_MODEL="claude-sonnet-4-20250514"

# Çıktı dizinini ayarlayın
export SPECTRA_OUTPUT_DIR="/path/to/analysis"
```

### JADX Entegrasyon Ayarları

**JADX GUI için:**
1. JADX'ı açın
2. File → Settings → Plugins → Spectra
3. Şunları yapılandırın:
   - Enable on startup: Yes
   - Auto-analyze: Yes
   - Show in menu: Yes

**JADX CLI için:**
```bash
# ~/.jadx/jadx.cfg dosyasına ekleyin
plugin.spectra.enabled=true
plugin.spectra.auto_analyze=true
plugin.spectra.config_path=/home/user/.jadx/plugins/spectra/config.json
```

## Doğrulama

### Kurulumu Test Edin

```bash
# Test 1: Eklenti bilgilerini kontrol edin
python spectra_jadx.py plugin-info

# Beklenen çıktı:
# {
#   "name": "Spectra",
#   "version": "1.2.5",
#   "environment": "standalone",
#   "spectra_available": true
# }

# Test 2: Örnek APK analiz edin
python spectra_jadx.py analyze test.apk -o /tmp/test_analysis

# Test 3: Arama işlevselliği
python spectra_jadx.py search test.apk "API_KEY"

# Test 4: Etkileşimli mod
echo "quit" | python spectra_jadx.py interactive test.apk
```

### JADX Entegrasyonunu Doğrulayın

```bash
# JADX'ın Spectra eklentisini algılayıp algılamadığını kontrol edin
jadx --list-plugins | grep spectra

# Veya eklenti dizinini manuel olarak kontrol edin
ls -la ~/.jadx/plugins/spectra/

# Beklenen dosyalar:
# spectra_jadx.py
# spectra/ (modül dizini)
# plugin.json
# config.json
# README.md
```

### IDA Pro Entegrasyonunu Doğrulayın

```bash
# IDA Pro Python konsolunda:
import spectra.jadx
print(spectra.jadx.__file__)

# jadx/api.py dosyasının yolunu göstermeli
```

### Binary Ninja Entegrasyonunu Doğrulayın

```bash
# Binary Ninja Python konsolunda:
import spectra.jadx
print(spectra.jadx.__file__)

# jadx/api.py dosyasının yolunu göstermeli
```

## Sorun Giderme

### Yaygın Sorunlar

#### Sorun 1: "JADX not found"

**Çözüm:**
```bash
# JADX'ın PATH'te olup olmadığını kontrol edin
which jadx

# Bulunamazsa, JADX yükleyin:
# macOS
brew install jadx

# Linux
wget https://github.com/skylot/jadx/releases/download/v1.4.7/jadx-1.4.7.zip
unzip jadx-1.4.7.zip
sudo ln -s $(pwd)/jadx-1.4.7/bin/jadx /usr/local/bin/jadx

# Veya jadx yolunu açıkça belirtin
python spectra_jadx.py analyze app.apk --jadx /path/to/jadx
```

#### Sorun 2: "Spectra core not available"

**Çözüm:**
```bash
# spectra modülüne erişilebilir olup olmadığını kontrol edin
python -c "import spectra; print(spectra.__version__)"

# Bulunamazsa, PYTHONPATH'e ekleyin
export PYTHONPATH="/path/to/Spectra:$PYTHONPATH"

# Veya Spectra bağımlılıklarını yükleyin
pip install anthropic httpx cryptography
```

#### Sorun 3: Eklenti JADX'da yüklenmiyor

**Çözüm:**
```bash
# Eklenti dizini izinlerini kontrol edin
ls -la ~/.jadx/plugins/spectra/

# plugin.json dosyasının var olduğunu ve geçerli olduğunu sağlayın
cat ~/.jadx/plugins/spectra/plugin.json | python -m json.tool

# Eklentiyi yeniden yükleyin
rm -rf ~/.jadx/plugins/spectra
python install_jadx_plugin.py
```

#### Sorun 4: Ortam algılama yanlış

**Çözüm:**
```bash
# Belirli bir ortamı zorlayın
python spectra_jadx.py analyze app.apk --env standalone

# Algılanan ortamı kontrol edin
python spectra_jadx.py plugin-info
```

#### Sorun 5: İzin hataları

**Çözüm:**
```bash
# Komut dosyasını yürütülebilir yapın
chmod +x spectra_jadx.py

# Eklenti dizini izinlerini düzeltin
chmod -R 755 ~/.jadx/plugins/spectra/
```

### Hata Ayıklama Modu

```bash
# Hata ayıklama günlüklemesini etkinleştirin
export SPECTRA_DEBUG=1
export SPECTRA_LOG_LEVEL=debug

# Ayrıntılı çıktı ile çalıştırın
python spectra_jadx.py analyze app.apk -o ./output --verbose
```

### Yardım Alma

```bash
# Yardım göster
python spectra_jadx.py --help

# Sürümü göster
python spectra_jadx.py --version

# Eklenti durumunu kontrol et
python spectra_jadx.py plugin-info
```

## Gelişmiş Kurulum

### Özel Kurulum Dizini

```bash
# Özel konuma yükleyin
export JADX_PLUGIN_DIR="/opt/spectra/plugins"
mkdir -p "$JADX_PLUGIN_DIR"

# Dosyaları kopyalayın
cp spectra_jadx.py "$JADX_PLUGIN_DIR/"
cp -r spectra "$JADX_PLUGIN_DIR/"

# Sembolik bağ oluşturun
ln -s "$JADX_PLUGIN_DIR/spectra_jadx.py" ~/.local/bin/spectra-jadx
```

### Sistem Çapında Kurulum

```bash
# Tüm kullanıcılar için yükleyin
sudo mkdir -p /opt/spectra/plugins
sudo cp spectra_jadx.py /opt/spectra/plugins/
sudo cp -r spectra /opt/spectra/plugins/

# Sistem çapında başlatıcı oluşturun
sudo tee /usr/local/bin/spectra-jadx << 'EOF'
#!/bin/bash
python /opt/spectra/plugins/spectra_jadx.py "$@"
EOF

sudo chmod +x /usr/local/bin/spectra-jadx
```

### Geliştirme Kurulumu

```bash
# Geliştirme modunda yükleyin
cd /path/to/Spectra

# Geliştirme ortamı oluşturun
python -m venv venv
source venv/bin/activate

# Düzenlenebilir modda yükleyin
pip install -e .

# Eklenti Spectra'nın geliştirme sürümünü kullanacak
python spectra_jadx.py analyze app.apk -o ./output
```

## Kaldırma

### Tam Kaldırma

```bash
# JADX eklentisini kaldırın
rm -rf ~/.jadx/plugins/spectra

# Bağımsız kurulumu kaldırın
rm -f ~/.local/bin/spectra-jadx
rm -f /usr/local/bin/spectra-jadx

# Yapılandırmayı kaldırın
rm -f ~/.jadx/plugins/spectra/config.json

# Not: IDA/Binary Ninja entegrasyonu kalır
# Spectra'yı tamamen kaldırmak için, bu platformlardan kaldırın
```

### Sadece Eklenti Kaldırma

```bash
# Spectra çekirdeğini tutun, sadece JADX eklentisini kaldırın
rm -rf ~/.jadx/plugins/spectra

# Spectra IDA/Binary Ninja'da çalışmaya devam eder
```

### Yükseltme

### Eklentiyi Yükseltin

```bash
cd /path/to/Spectra
git pull origin main  # Veya yeni sürümü indirin

# Eklentiyi yeniden yükleyin
python install_jadx_plugin.py --force
```

### Güncellemeleri Kontrol Edin

```bash
# Geçerli sürümü kontrol edin
python spectra_jadx.py --version

# En son sürümle karşılaştırın
curl -s https://api.github.com/repos/alicangnll/Spectra/releases/latest | grep tag_name
```

## Sonraki Adımlar

Kurulumdan sonra:

1. **API anahtarını yapılandırın** (AI özelliklerini kullanıyorsanız):
   ```bash
   # Yapılandırmayı düzenleyin
   nano ~/.jadx/plugins/spectra/config.json

   # API anahtarınızı ayarlayın
   # "api_key": "your-api-key-here"
   ```

2. **Örnek APK ile test edin**:
   ```bash
   python spectra_jadx.py analyze sample.apk -o ./test_analysis
   ```

3. **Özellikleri keşfedin**:
   - Ayrıntılı kullanım için [JADX_README.md](JADX_README.md) dosyasını okuyun
   - Etkileşimli modu deneyin: `python spectra_jadx.py interactive app.apk`
   - Güvenlik değerlendirme özelliklerini kontrol edin

4. **İş akışıyla entegre edin**:
   - CI/CD işlem hattına ekleyin
   - Derin analiz için IDA Pro ile kullanın
   - Modern analiz için Binary Ninja ile kullanın

## Destek

Sorular ve sorunlar için:
- **Belgeler:** [JADX_README.md](JADX_README.md)
- **Sorunlar:** https://github.com/alicangnll/Spectra/issues
- **Tartışmalar:** https://github.com/alicangnll/Spectra/discussions

## Ek: Kurulum Dizin Yapısı

```
~/.jadx/plugins/spectra/
├── spectra_jadx.py          # Ana eklenti komut dosyası (yürütülebilir)
├── plugin.json              # JADX eklenti meta verileri
├── config.json              # Eklenti yapılandırması
├── README.md                # Bu dosya
└── spectra/                  # Spectra çekirdek modülü
    ├── jadx/
    │   ├── __init__.py
    │   └── api.py           # JADX API sarmalayıcı
    ├── core/
    │   ├── config.py       # Yapılandırma yönetimi
    │   ├── logging.py      # Günlükleme yardımcı programları
    │   └── crypto.py       # Şifreleme yardımcı programları
    ├── tools/
    │   └── ...             # Analiz araçları
    └── skills/
        └── builtins/
            └── jadx-analysis/
                └── skill.md  # Yetenek tanımı
```
