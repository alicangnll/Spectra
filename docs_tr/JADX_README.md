# Spectra JADX Eklentisi - Hibrit Android APK Analiz Sistemi

Spectra'nın çok modlu Android APK analiz sistemi şu şekillerde çalışır:
- **Bağımsız CLI aracı** - Terminalden bağımsız analiz
- **IDA Pro entegrasyonu** - IDA Pro'nun Spectra'sı içinde gömülü
- **Binary Ninja entegrasyonu** - Binary Ninja'nın Spectra'sı içinde gömülü
- **JADX native eklenti** - JADX Decompiler içinde yüklenebilir

## Özellikler

**Kapsamlı APK Analizi:**
- JADX kullanarak APK'ları Java kaynak koduna dönüştürme
- Paket yapısını ve bileşenlerini analiz etme
- AndroidManifest.xml'i ayrıştırma ve meta veri çıkarma
- Dönüştürülen kodda dize arama (API anahtarları, uç noktalar, kimlik bilgileri)
- Native kütüphaneleri (.so dosyaları) bulma ve mimarileri algılama
- Sınıf bağımlılıklarını ve kalıtım hiyerarşilerini analiz etme
- Güvenlik değerlendirmesi ve açık tespiti
- Kötü amaçlı yazılım analizi ve tehdit istihbaratı
- AI destekli interaktif analiz modu

**Çoklu Ortam Desteği:**
- Otomatik ortam algılama ile 4 farklı modda çalışır
- Tüm platformlarda tutarlı API (bağımsız, IDA, Binary Ninja, JADX)
- Tüm modlarda paylaşılan yapılandırma ve bulgular
- Mevcut reverse engineering iş akışlarıyla sorunsuz entegrasyon

## Kurulum

### Hızlı Kurulum (Tüm Modlar)

```bash
# Spectra'yı klonlayın veya indirin
cd /path/to/Spectra

# Otomatik kurucuyu çalıştırın (JADX, IDA, Binary Ninja'yi algılar)
python install_jadx_plugin.py
```

Bu işlem:
1. Yüklü platformları algılar (JADX, IDA Pro, Binary Ninja)
2. Spectra'yı JADX native eklentisi olarak kurar
3. IDA/Binary Ninja Spectra ile entegrasyonu etkinleştirir
4. Yapılandırma dosyalarını ve bağımlılıkları ayarlar

### Modlara Göre Manuel Kurulum

#### Mod 1: JADX Native Eklenti

**JADX'i Kurun:**
```bash
# macOS
brew install jadx

# Linux
wget https://github.com/skylot/jadx/releases/download/v1.4.7/jadx-1.4.7.zip
unzip jadx-1.4.7.zip
sudo ln -s $(pwd)/jadx-1.4.7/bin/jadx /usr/local/bin/jadx

# Windows - https://github.com/skylot/jadx/releases adresinden indirin
```

**JADX Eklentisi Olarak Kurun:**
```bash
cd /path/to/Spectra

# Otomatik kurucuyu çalıştırın
python install_jadx_plugin.py

# Veya manuel olarak JADX eklenti dizinine kurun
mkdir -p ~/.jadx/plugins/spectra
cp spectra_jadx.py ~/.jadx/plugins/spectra/
cp -r spectra ~/.jadx/plugins/spectra/

# Eklenti config'ini oluşturun
cat > ~/.jadx/plugins/spectra/plugin.json << 'EOF'
{
  "name": "Spectra",
  "version": "1.2.5",
  "description": "AI-powered Android APK analysis assistant",
  "author": "Ali Can Gönüllü",
  "main": "spectra_jadx.py",
  "enabled": true
}
EOF
```

#### Mod 2: Bağımsız CLI Aracı

```bash
cd /path/to/Spectra

# PATH'e kopyalayın
cp spectra_jadx.py ~/.local/bin/spectra-jadx
chmod +x ~/.local/bin/spectra-jadx

# Veya doğrudan kullanın
python spectra_jadx.py analyze app.apk -o ./decompiled
```

#### Mod 3: IDA Pro Entegrasyonu

```bash
# Spectra önce IDA Pro'ya kurulmalıdır
# JADX entegrasyonu /jadx skill'i üzerinden otomatiktir

# IDA Pro'da:
Ctrl+Shift+I → Spectra panelini açar
/jadx Bu APK'yı analiz et /path/to/app.apk
/jadx Bu uygulama hangi izinleri istiyor?
/jadx MainActivity sınıfını bul
```

#### Mod 4: Binary Ninja Entegrasyonu

```bash
# Spectra önce Binary Ninja'ya kurulmalıdır
# JADX entegrasyonu /jadx skill'i üzerinden otomatiktir

# Binary Ninja'da:
Tools → Spectra → Open Chat
/jadx Bu APK'yı analiz et /path/to/app.apk
/jadx Sabitlenmiş API anahtarlarını ara
/jadx Native kütüphaneleri kontrol et
```

## Kullanım

### Bağımsız CLI Modu

```bash
# APK analizi
python spectra_jadx.py analyze app.apk -o ./decompiled

# Dize arama
python spectra_jadx.py search app.apk "API_KEY"
python spectra_jadx.py search app.apk "http://" --case-sensitive

# Paket yapısını göster
python spectra_jadx.py structure app.apk --export structure.json

# Belirli bir sınıfı analiz et
python spectra_jadx.py class app.apk com.example.app.MainActivity

# İnteraktif AI modu
python spectra_jadx.py interactive app.apk

# Eklenti bilgisini göster
python spectra_jadx.py plugin-info
```

### JADX Native Eklenti Modu

**JADX GUI'den:**
```
Tools → Spectra → Analyze APK
Tools → Spectra → Search Strings
Tools → Spectra → Security Assessment
Tools → Spectra → Interactive Mode
```

**JADX CLI'den:**
```bash
# Spectra eklentisiyle normal JADX
jadx --plugin spectra app.apk -d output

# Veya Spectra'yı doğrudan çağırın
python ~/.jadx/plugins/spectra/spectra_jadx.py analyze app.apk -o output
```

### IDA Pro Entegrasyon Modu

```
# IDA Pro'da Spectra panelini açın (Ctrl+Shift+I)
/jadx Bu APK'yı analiz et /path/to/app.apk
/jadx Ana giriş noktaları nelerdir?
/jadx Şüpheli izinleri bul
/jadx C2 alan adlarını ara
```

### Binary Ninja Entegrasyon Modu

```
# Binary Ninja'da Spectra'yı açın (Ctrl+Shift+I)
/jadx Bu APK'yı analiz et /path/to/app.apk
/jadx Sabitlenmiş gizli anahtarları kontrol et
/jadx Ağ iletişimini analiz et
```

## Ortam Algılama

Eklenti çalıştırma ortamını otomatik olarak algılar:

```python
# Bağımsız CLI
$ python spectra_jadx.py analyze app.apk
Environment: STANDALONE

# JADX içinde
$ jadx --plugin spectra app.apk
Environment: JADX

# IDA Pro içinde
/jadx Analyze...
Environment: IDA

# Binary Ninja içinde
/jadx Analyze...
Environment: BINARY_NINJA
```

## Python API

Tüm modlar aynı Python API'yi destekler:

```python
from spectra.jadx import JadxAnalyzer

# Analyzers başlat
analyzer = JadxAnalyzer()

# APK'yı dönüştür
decompiled_dir = analyzer.decompile_apk("app.apk", "./output")

# Yapıyı analiz et
structure = analyzer.get_package_structure(decompiled_dir)
print(f"Toplam sınıf: {structure['total_classes']}")

# Manifest'i ayrıştır
manifest = analyzer.find_android_manifest(decompiled_dir)
print(f"Paket: {manifest['package']}")
print(f"İzinler: {manifest['permissions']}")

# Dizeleri ara
matches = analyzer.search_string_in_sources(decompiled_dir, "API_KEY")
for match in matches:
    print(f"{match['file']}:{match['line']} - {match['content']}")

# Sınıfı analiz et
class_info = analyzer.get_class_dependencies(decompiled_dir, "com.example.MainActivity")
print(f"Metodlar: {class_info['methods']}")

# Native kütüphaneleri bul
native_libs = analyzer.find_native_libraries(decompiled_dir)
print(f"Native kütüphaneler: {native_libs}")

# Analizi dışa aktar
analyzer.export_to_json(decompiled_dir, "analysis.json")
```

## Yapılandırma

Eklenti davranışı `config.json` üzerinden yapılandırılabilir:

**Konum:** `~/.jadx/plugins/spectra/config.json`

```json
{
  "auto_analyze": true,
  "ai_provider": "anthropic",
  "api_key": "your-api-key-here",
  "max_tokens": 8192,
  "model": "claude-sonnet-4-20250514",
  "security_checks": {
    "permissions": true,
    "hardcoded_secrets": true,
    "network_security": true,
    "native_libraries": true,
    "debuggable_check": true,
    "backup_check": true
  },
  "output_formats": {
    "json": true,
    "markdown": true,
    "xml": false
  }
}
```

## Örnekler

### Kötü Amaçlı Yazılım Analizi

```bash
# Şüpheli APK analiz et
python spectra_jadx.py analyze suspicious.apk -o ./malware_analysis

# Otomatik güvenlik değerlendirmesi
# - Risk puanı hesaplama (0-100)
# - Tehlikeli izin tespiti
# - Sabitlenmiş gizli anahtar arama
# - Hata ayıklamaya izin veren derleme tespiti
# - Güvensiz depolama tespiti

# C2 alan adlarını ara
python spectra_jadx.py search suspicious.apk "http://"

# Native kod kontrolü
python spectra_jadx.py class suspicious.apk com.example.NativeLib
```

### Penetrasyon Testi

```bash
# Hedef uygulamayı dönüştür
python spectra_jadx.py analyze target.apk -o ./target_app

# API uç noktalarını bul
python spectra_jadx.py search target.apk "api."

# Sabitlenmiş gizli anahtarları kontrol et
python spectra_jadx.py search target.apk "password"
python spectra_jadx.py search target.apk "token"
python spectra_jadx.py search target.apk "secret"

# Ağ iletişimini analiz et
python spectra_jadx.py search target.apk "https://"
```

### Açık Araştırması

```bash
# İnteraktif derinlemesine analiz
python spectra_jadx.py interactive app.apk

> Giriş noktaları nelerdir?
> Dışa aktarılan tüm activity'leri göster
> Kripto API kullanımını bul
> SQL enjeksiyon vektörlerini kontrol et
> SSL sertifika doğrulamasını analiz et
```

## Spectra Ekosistemi ile Entegrasyon

### Bulguları İşaretleme

IDA Pro veya Binary Ninja modlarında kullanıldığında:

```
/jadx Bu APK'yı analiz et ve kritik bulguları işaretle
# Analizde [FINDING:0x...] bağlantıları oluşturur
# Kategoriler: Critical, Suspicious, Verified, vb.
```

### Şüpheli API Vurgulama

```
/jadx Hangi tehlikeli API'ler kullanılıyor?
# Otomatik vurgular: CreateRemoteThread, WriteProcessMemory, vb.
# Şiddete göre renk kodlaması ve MITRE ATT&CK referansları
```

### Anti-Hata Ayıklama Tespiti

```
/jadx Anti-hata ayıklama tekniklerini kontrol et
# Tespiter: IsDebuggerPresent, PEB kontrolleri, zaman saldırıları
# Belirli konumları ve kod kalıplarını raporlar
```

## Gelişmiş Özellikler

### Toplu Analiz

```bash
# Birden fazla APK'yi analiz et
for apk in *.apk; do
    python spectra_jadx.py analyze "$apk" -o "analysis_$(basename $apk .apk)" --export "reports/$(basename $apk .apk).json"
done
```

### CI/CD Entegrasyonu

```bash
# Derleme hattında
python spectra_jadx.py analyze app-release.apk --security-check --export security_report.json

# Risk puanını kontrol et
RISK_SCORE=$(python -c "import json; print(json.load(open('security_report.json'))['security_assessment']['risk_score'])")

if [ $RISK_SCORE -gt 50 ]; then
    echo "Yüksek risk tespit edildi, dağıtım engelleniyor"
    exit 1
fi
```

### Özel Analiz Scriptleri

```python
from spectra.jadx import JadxAnalyzer

analyzer = JadxAnalyzer()


# Özel güvenlik kontrolü
def check_malware_indicators(apk_path: str) -> dict:
    decompiled_dir = analyzer.decompile_apk(apk_path, "/tmp/temp_analysis")

    indicators = {"suspicious_permissions": [], "hardcoded_secrets": [], "native_code": False, "obfuscation": False}

    # İzinleri kontrol et
    manifest = analyzer.find_android_manifest(decompiled_dir)
    dangerous = ["android.permission.SEND_SMS", "android.permission.READ_SMS"]
    indicators["suspicious_permissions"] = [p for p in manifest["permissions"] if p in dangerous]

    # Gizli anahtarları kontrol et
    secret_patterns = ["api_key", "password", "token"]
    for pattern in secret_patterns:
        matches = analyzer.search_string_in_sources(decompiled_dir, pattern)
        indicators["hardcoded_secrets"].extend(matches)

    # Native kod kontrolü
    native_libs = analyzer.find_native_libraries(decompiled_dir)
    indicators["native_code"] = len(native_libs) > 0

    return indicators
```

## Sorun Giderme

### JADX'te Eklenti Yüklenmiyor

1. Eklenti dizinini kontrol edin:
```bash
ls -la ~/.jadx/plugins/spectra/
```

2. JADX sürümünü doğrulayın:
```bash
jadx --version  # 1.4.7 veya üzeri olmalı
```

3. Eklenti meta verilerini kontrol edin:
```bash
cat ~/.jadx/plugins/spectra/plugin.json
```

### Eksik Bağımlılıklar

```bash
# Python bağımlılıkları
pip install anthropic httpx cryptography

# JADX kurulumu
brew install jadx  # macOS
# veya GitHub releases'ten indirin
```

### Ortam Algılama Sorunları

```bash
# Hangi ortamın algılandığını kontrol edin
python spectra_jadx.py plugin-info

# Belirli bir modu zorlayın
python spectra_jadx.py analyze app.apk --env standalone
```

## Mimari

```
spectra_jadx.py (Hibrit Eklenti)
├── Ortam Algılama
│   ├── Bağımsız CLI modu
│   ├── IDA Pro entegrasyonu
│   ├── Binary Ninja entegrasyonu
│   └── JADX native eklenti modu
├── JadxPluginWrapper
│   ├── Çalıştırma ortamını otomatik algıla
│   ├── Mode göre başlat
│   └── Birleşik API sağla
├── Komut İşleyiciler
│   ├── analyze - Tam APK analizi
│   ├── search - Dize arama
│   ├── structure - Paket yapısı
│   ├── class - Sınıf analizi
│   └── interactive - AI modu
└── spectra/
    ├── jadx/api.py - JADX sarmalayıcı
    ├── core/ - Temel işlevler
    └── tools/ - Ek araçlar
```

## Sürüm Uyumluluğu

- **JADX:** 1.4.7+
- **Python:** 3.10+
- **IDA Pro:** 7.5+ (Spectra kurulmuş)
- **Binary Ninja:** 3.4+ (Spectra kurulmuş)
- **OS:** Linux, macOS, Windows

## Lisans

MIT License - Ayrıntılar için LICENSE dosyasına bakın

## Destek & Katkıda Bulunma

- **Sorunlar:** https://github.com/alicangnll/Spectra/issues
- **Dokümantasyon:** https://github.com/alicangnll/Spectra/tree/main/docs
- **Katkıda Bulunma:** Pull requests hoş karşılanır!

## Değişiklik Günlüğü

### v1.2.5 (Güncel)
- Hibrit eklenti sistemi eklendi (4 mod)
- Ortam otomatik algılama
- Tüm platformlarda birleşik API
- Geliştirilmiş güvenlik değerlendirmesi
- CI/CD entegrasyon desteği
- Toplu analiz yetenekleri

### v1.0.0
- İlk bağımsız CLI sürümü
- Temel JADX entegrasyonu
- Python API desteği
