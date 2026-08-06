# Spectra Mimari Dokümantasyonu

Spectra reverse engineering agent sistemi için kapsamlı teknik referans.

## Genel Bakış

Spectra, IDA Pro ve Binary Ninja ile doğrudan entegre olan AI destekli bir reverse engineering asistanıdır. Akışlı yanıtlar, araç orkestrasyonu ve kalıcı hafıza ile agent döngü mimarisi sunar.

## Çekirdek Mimari

### Agent Döngüsü

Spectra'ın kalbi, `spectra/agent/loop.py` dosyasında uygulanan generator tabanlı agent döngüsüdür:

```python
def run(user_message: str) -> Generator[TurnEvent, None, None]:
    # 1. Komutları ayrıştır ve yetenekleri çöz
    # 2. Sistem istemini binary bağlamıyla oluştur
    # 3. LLM yanıtını token token akıt
    # 4. Araç çağrılarını çalıştır
    # 5. Sonuçları LLM'e geri besle
    # 6. Tamamlanana kadar tekrarla
```

### Turn Event Sistemi

Agent döngüsü ile arayüz arasındaki iletişim `TurnEvent` nesnelerini kullanır:

- `TEXT_DELTA` - Akışlı metin tokenları
- `TOOL_CALL_START` - Araç çağrısı başlar
- `TOOL_RESULT` - Araç çalıştırma sonucu
- `TURN_START` / `TURN_END` - Turn sınırları
- `ERROR` - Hata koşulları
- `MUTATION_RECORDED` - Veritabanı değişikliği takibi

## Araç Çerçevesi

### Araç Tanımlama

Araçlar `@tool` dekoratörü kullanılarak tanımlanır:

```python
@tool(category="functions", mutating=True)
def rename_function(old_name: str, new_name: str) -> str:
    """Veritabanındaki bir fonksiyonu yeniden adlandır."""
    # Uygulama
```

### Araç Kayıt Defteri

`spectra/tools/registry.py` dosyasındaki merkezi kayıt defteri şunları yönetir:
- Araç keşfi ve kaydı
- Parametre doğrulama (gerekli parametreler çalıştırmadan önce kontrol edilir)
- Argüman türü zorlama (LLM dostu tür dönüşümü)
- Zaman aşımı ile yürütme
- Geri alma için ters işlem takibi

### Parametre Doğrulama

Herhangi bir aracı çalıştırmadan önce, kayıt defteri gerekli parametrelerin var olduğunu doğrular:

```python
# Gerekli parametrelerin var olduğunu doğrula
missing = []
for param in defn.parameters:
    if param.required and param.name not in arguments:
        missing.append(param.name)
if missing:
    raise ToolValidationError(
        f"Tool {name} missing required parameters: {', '.join(missing)}"
    )
```

Bu, anlaşılır olmayan TypeError mesajlarını önler ve LLM'e hangi parametrelerin eksik olduğu konusunda net geri bildirim sağlar.

### Araç Kategorileri

- **Navigation** - Hareket ve konumlama
- **Functions** - Fonksiyon analizi ve manipülasyonu
- **Strings** - Arama ve dize çıkarma
- **Database** - Segment, içe/dışa aktarma sorguları
- **Disassembly** - Assembly listeleme
- **Decompiler** - Sözde kod üretimi
- **Xrefs** - Çapraz referans sorguları
- **Annotations** - Yeniden adlandırma ve yorumlama
- **Types** - Yapı ve tür manipülasyonu
- **Scripting** - Onay ile Python yürütme

## Yetenekler Sistemi

### Yetenek Formatı

Yetenekler, YAML ön verisi olan Markdown dosyalarıdır:

```markdown
---
name: Malware Analysis
description: Windows PE malware analizi iş akışı
tags: [malware, windows]
allowed_tools: [decompile_function, list_imports, search_strings]
mode: exploration
---
Task: Bu ikili dosyayı olası malware olarak analiz et.
```

### Yetenek Aktivasyonu

`/` ile başlayan komutlar yetenekleri tetikler:
- `/malware-analysis` - Malware analizi yeteneğini aktifleştir
- `/deobfuscation` - Deobfuscation iş akışını aktifleştir
- `/modify <goal>` - Binary değiştirme moduna gir

### Yerleşik Yetenekler

Şunları kapsayan 33 yerleşik yetenek:
- Bellek bozulması ve exploit
- Reverse engineering teknikleri
- Protokol analizi
- Kriptografik analiz
- Firmware RE
- Mobil uygulama analizi
- Web uygulama güvenliği
- CTF yardımcı programları

## Keşif Modu

### Dört Fazlı Akış

Keşif modu otonom ikili dosya analizi uygular:

1. **EXPLORE** - Binary yapısını haritala
2. **PLAN** - Değişiklik planı sentezle
3. **EXECUTE** - Yamaları uygula
4. **SAVE** - Değişiklikleri kalıcı hale getir

### Bilgi Tabanı

Keşif sırasında bulguları biriktirir:
- `relevant_functions` - Keşfedilen fonksiyonlar
- `findings` - Yapılandırılmış gözlemler
- `hypotheses` - Çıkarılan davranışlar

### Subagentler

Paralel analiz için izole agent örnekleri:
- Temiz bağlam pencereleri
- Bağımsız araç yürütme
- Sonuç sentezi

## Arayüz Katmanı

### Panel Mimaris

`spectra/ui/panel_core.py` dosyasındaki paylaşılan panel çekirdeği:
- Mesaj geçmişi ile sohbet arayüzü
- Araç yürütme görüntüsü
- Değişiklik takip paneli
- Model bilgisi ile bağlam çubuğu

### Olay Polling

QTimer, agent çıktısını 50ms aralıklarla poll eder:
- Arka plan iş parçacığından olayları deque yapar
- Uygun UI bileşenlerine yönlendirir
- Kullanıcı etkileşimlerini işler

### Oturum Yönetimi

Çok sekmeli oturumlar şunlarla:
- Bağımsız sohbet geçmişleri
- Token kullanımı takibi
- Oturum kalıcılığı
- Fork ve birleştirme işlemleri

## Sağlayıcı Katmanı

### LLM Sağlayıcıları

Şunları destekleyen soyutlanmış sağlayıcı arayüzü:
- Anthropic Claude (prompt caching ile)
- OpenAI uyumlu API'ler
- Google Gemini
- Ollama (yerel modeller)
- Özel uç noktalar

### Akışlı Yanıtlar

Token token akış şunları sağlar:
- Gerçek zamanlı geri bildirim
- İlerleyen araç çağrısı görüntüsü
- Erken hata tespiti

### Yeniden Deneme Mantığı

Üstel geri çekme ile otomatik yeniden deneme:
- Oran sınırı işleme
- Geçici hata kurtarma
- Yeniden deneme sırasında kullanıcı bildirimi

## Bağlam Yönetimi

### Pencere Yönetimi

Akıllı bağlam penceresi işleme:
- Token sayma ve tahmin
- %80 eşikinde mesaj sıkıştırma
- Baş ve kuyruk korunması
- Orta mesaj özetleme

### Kalıcı Hafıza

`SPECTRA.md` dosyaları oturumlar arası bulguları depolar:
- Binary başına hafıza
- Başlangıçta otomatik yükleme
- Araç veya açık komut ile kaydetme

## Değişiklik Takibi

### Geri Alma Sistemi

Her veritabanı değişikliği takip edilir:
- Öncesi durumu yakalama
- Ters işlem üretimi
- Değişiklik günlüğü paneli görüntüsü
- Geri alma komutu desteği

### Tersine Dönülebilir İşlemler

Desteklenen değişiklikler:
- Fonksiyon yeniden adlandırma
- Değişken yeniden adlandırma
- Yorum ayarlama
- Tür değişiklikleri

Tersine dönülemez işlemler:
- `execute_python` komut dosyaları
- Binary yamalama

## İş Parçacığı Güvenliği

### IDA Pro Entegrasyonu

Tüm IDA API çağrıları `@idasync` dekoratörü ile ana iş parçacığına marshal edilir:
- Otomatik iş parçacığı değiştirme
- Arka plandan senkron yürütme
- IDA'nın Python sınırlamaları için güvenlik

### Binary Ninja

İş parçacığı güvenli API, arka plan iş parçacıklarından doğrudan çağrıya izin verir.

## MCP Entegrasyonu

### Sunucu Yönetimi

MCP sunucu desteği şunları sağlar:
- Dış araç entegrasyonu
- Özel sunucu yapılandırması
- Sağlık izleme
- Araç şeması köprüleme

### Yapılandırma

`~/.spectra/mcp_servers.json` kullanılabilir sunucuları ve araç kümelerini tanımlar.

## Performans Optimizasyonları

### Prompt Önbelleğe Alma

Anthropic'e özel optimizasyon:
- Önbellek kontrol başlıkları
- Sistem istemi önbelleğe alma
- Uzun konuşmalar için düşük maliyetler

### Araç Toplu İşleme

Bağımsız işlemler için paralel araç yürütme:
- Birden çok decompilation isteği
- Toplu xref sorguları
- Eş zamanlı yeniden adlandırma işlemleri

### Sonuç Kırpma

Büyük araç sonuçları şunlara kırpılır:
- Bağlam patlamasını önlemek
- Token bütçesini korumak
- Kritik bilgileri korumak

## Hata İşleme

### Exception Hiyerarşisi

Yapılandırılmış hata türleri:
- `AgentError` - Döngü düzeyi hataları
- `CancellationError` - Kullanıcı iptali
- `ProviderError` - LLM API sorunları
- `ToolError` - Araç yürütme hataları
- `MCPError` - MCP protokol sorunları

### Ardışık Hata Takibi

Üst üste üç araç hatası şunları tetikler:
- Geçici araç devre dışı bırakma
- Sadece metin yedek modu
- Kullanıcı bildirimi

## Günlük Kaydı

### Çok Çıktılı Günlük Kaydı

Günlükler şunlara yazılır:
- IDA çıktı penceresi (INFO seviyesi)
- Hata ayıklama dosyası (fsync ile DEBUG seviyesi)
- Makine ayrıştırması için yapılandırılmış JSONL

### Günlük Konumları

- `~/.spectra/spectra_debug.log` - İnsan okunabilir
- `~/.spectra/spectra_structured.jsonl` - Makine ayrıştırılabilir

## Güvenlik

### Python Yürütme

`execute_python` aracı şunları gerektirir:
- Açık kullanıcı onayı
- Yürütmeden önce kod görüntüleme
- Onay başına önbelleğe alma
- Güvenlik uyarıları

### Binary Güvenliği

Agent'tan açıkca kaçınılan:
- Hedef binaryleri çalıştırma
- Sandbox dışında dosya sistemi yazmaları
- Onay olmad ağ işlemleri

## Genişletme Noktaları

### Özel Araçlar

Araç ekleyin:
1. `@tool` dekoratörü ile fonksiyon oluşturun
2. Uygun kayıt defterine ekleyin
3. Araç listesini yeniden oluşturun

### Özel Yetenekler

Yetenek oluşturun:
1. Yetenekler dizininde Markdown dosyası oluşturun
2. YAML ön verisi ekleyin
3. Görev talimatlarını uygulayın

### MCP Sunucuları

Şunlarla işlevselliği genişletin:
1. `mcp_servers.json` içinde sunucu yapılandırın
2. Sunucu araçları otomatik kaydedilir
3. Tüm oturumlarda kullanılabilir

## Geliştirme İş Akışı

### Özellik Ekleme

1. Araç veya yetenek uygulayın
2. Gerekirse test ekleyin
3. Dokümantasyonu güncelleyin
4. Pull request gönderin

### Hata Ayıklama

Hata ayıklama günlüklemesini etkinleştirin:
```bash
export SPECTRA_DEBUG=1
```

Günlükleri gerçek zamanlı olarak görün:
```bash
tail -f ~/.spectra/spectra_debug.log
```

## Mimari Kararlar

### Generator Tabanlı Döngü

Gerekçe:
- Akışlı yanıtları etkinleştirir
- Olay işlemeyi basitleştirir
- İptali destekler
- Endişelerin temiz ayrımı

### İş Süreci İçi Araç Yürütme

Gerekçe:
- Araç çağrıları için sıfır gecikme
- Doğrudan veritabanı erişimi
- IPC ek yükü yok
- Tasarım gereği iş parçacığı güvenli

### Kalıcı Hafıza Dosyaları

Gerekçe:
- Oturumlar arası süreklilik
- İnsan okunabilir depolama
- Düzenlemek ve gözden geçirmek kolay
- Git takip edilebilir bulgular

---

Uygulama ayrıntıları için `spectra/` dizinindeki kaynak koda bakın.
Kullanım talimatları için [README.md](README.md) dosyasına bakın.
