# Spectra MCP Sunucu Kılavuzu

> Spectra'da Model Context Protocol (MCP) sunucularını yönetme için tam kılavuz

---

## İçindekiler

1. [Giriş](#1-giriş)
2. [MCP Kategorilerini Anlama](#2-mcp-kategorilerini-anlama)
3. [MCP Sunucuları Ekleme](#3-mcp-sunucuları-ekleme)
4. [Mevcut Sunucuları Yönetme](#4-mevcut-sunucuları-yönetme)
5. [MCP Sunucu Yapılandırması](#5-mcp-sunucu-yapılandırması)
6. [Popüler MCP Sunucuları](#6-popüler-mcp-sunucuları)
7. [Sorun Giderme](#7-sorun-giderme)
8. [Güvenlik Hususları](#8-güvenlik-hususları)

---

## 1. Giriş

### 1.1 MCP Sunucuları Nedir?

**MCP (Model Context Protocol)** sunucuları, Spectra'nın yeteneklerini analiz sırasında AI'in kullanabileceği harici araçlar ve veri kaynakları ile genişletir. Her MCP sunucusu belirli işlevsellik sunar:

- **Dosya sistemi erişimi** - Sisteminizdeki dosyaları okuma/yazma
- **Veritabanı sorguları** - SQL veritabanlarını sorgulama
- **Web kazıma** - Web içeriğini getirme ve analiz etme
- **Kod analizi** - Ekstra kod anlama araçları
- **Özel araçlar** - Kendi özel analiz yetenekleriniz

### 1.2 Spectra'da MCP Kategorileri

Spectra üç kategoride MCP sunucusunu destekler:

| Kategori | Kaynak | Açıklama | Yönetim |
|----------|--------|----------|---------|
| **Spectra MCP Sunucuları** | Manuel yapılandırma | Spectra'da yapılandırdığınız özel sunucular | Tam yönetilebilir (ekleme/kaldırma/düzenleme) |
| **Claude Code MCP Sunucuları** | Claude Code config'den otomatik algılanan | Claude Code'dan keşfedilen harici sunucular | Salt okunur (otomatik algılanır) |
| **Codex MCP Sunucuları** | Codex config'den otomatik algılanan | Codex'ten keşfedilen harici sunucular | Salt okunur (otomatik algılanır) |

---

## 2. MCP Kategorilerini Anlama

### 2.1 Spectra MCP Sunucuları (Önerilen)

Spectra içinde manuel olarak yapılandırdığınız ve yönettiğiniz MCP sunucuları:

**✅ Avantajları:**
- Yapılandırma üzerinde tam kontrol
- Sunucu ekleyebilir, kaldırabilir ve düzenleyebilirsiniz
- Spectra güncellemeleri arasında kalıcı
- Diğer araçlardan bağımsız çalışır

**📝 Ne zaman kullanılmalı:**
- MCP yapılandırması üzerinde tam kontrol istiyorsanız
- Claude Code veya Codex kullanmıyorsanız
- Başka yerde mevcut olmayan belirli MCP sunuculara ihtiyacınız varsa

### 2.2 Claude Code MCP Sunucuları

Claude Code yapılandırmanızdan otomatik olarak keşfedilen sunucular:

**✅ Avantajları:**
- Manuel yapılandırma gerekmez
- Claude Code kurulumunuzla senkronize olur
- Claude Code ile otomatik olarak açılır/kapanır

**📝 Ne zaman kullanılmalı:**
- Zaten Claude Code'u MCP sunucularıyla kullanıyorsanız
- Araçlar arasında tutarlılık istiyorsanız
- Otomatik yapılandırmayı tercih ediyorsanız

### 2.3 Codex MCP Sunucuları

Codex yapılandırmanızdan otomatik olarak keşfedilen sunucular:

**✅ Avantajları:**
- Codex'ten otomatik keşif
- Manuel kurulum gerekmez

**📝 Ne zaman kullanılmalı:**
- Codex MCP entegrasyonunu kullanıyorsanız
- Araçlar arasında paylaşılan yapılandırma istiyorsanız

---

## 3. MCP Sunucuları Ekleme

### 3.1 MCP Ayarlarına Erişim

1. IDA Pro veya Binary Ninja'da **Spectra'yı açın**
2. **⚙ Settings** butonuna tıklayın
3. **MCP** sekmesine gidin

### 3.2 Spectra MCP Sunucusu Ekleme

#### Adım 1: "+ Add Server" Butonuna Tıklayın

MCP sunucu kategori seçim diyaloğu açılacaktır:

```
┌─────────────────────────────────────────┐
│  MCP Sunucu Kategorisi Seçin           │
├─────────────────────────────────────────┤
│  Hangi tür MCP sunucusunu eklemek       │
│  istiyorsunuz?                          │
│                                         │
│  ◉ Spectra MCP Sunucuları              │
│    Spectra'da manuel olarak            │
│    yapılandırılan özel sunucular        │
│                                         │
│  ○ Claude Code MCP Sunucuları          │
│    Claude Code'dan harici sunucular     │
│    (salt okunur)                       │
│                                         │
│  ○ Codex MCP Sunucuları                │
│    Codex'ten harici sunucular           │
│    (salt okunur)                       │
│                                         │
│                    [İptal]  [İleri]   │
└─────────────────────────────────────────┘
```

#### Adım 2: "Spectra MCP Sunucuları" Seçin

#### Adım 3: Sunucu Detaylarını Doldurun

MCP Sunucu yapılandırma diyaloğu açılacaktır:

```
┌─────────────────────────────────────────┐
│  MCP Sunucusu Ekle                      │
├─────────────────────────────────────────┤
│  Sunucu Adı:     [________________]    │
│  Komut:          [________________]    │
│  Argümanlar:     [________________]    │
│  Ortam Değişkenleri: [______________]  │
│  Zaman Aşımı:    [30 ▲] saniye        │
│                                         │
│                    [İptal]  [Ekle]    │
└─────────────────────────────────────────┘
```

#### Adım 4: Sunucu Parametrelerini Yaplandırın

| Alan | Açıklama | Örnek |
|------|----------|-------|
| **Sunucu Adı** | Sunucu için benzersiz tanımlayıcı | `filesystem`, `postgres`, `web-scraper` |
| **Komut** | Sunucuyu başlatan çalıştırılabilir komut | `npx`, `uvx`, `python`, `/yol/sunucu` |
| **Argümanlar** | Sunucu için komut satırı argümanları | `-y @modelcontextprotocol/server-filesystem` |
| **Ortam** | İsteğe bağlı ortam değişkenleri (ANAHTAR=değer formatı) | `ALLOWED_PATHS=/tmp,/home/user/projects` |
| **Zaman Aşımı** | Sunucu yanıtını bekleme süresi (saniye) | `30.0` |

---

## 4. Mevcut Sunucuları Yönetme

### 4.1 Sunucuları Etkinleştirme/Devre Dışı Bırakma

**MCP Ayarları** sekmesinde:

**Spectra MCP Sunucuları için:**
- Her sunucunun yanındaki onay kutularını kullanın
- Değişiklikler yeni oturumlarda hemen uygulanır

**Claude Code / Codex Sunucuları için:**
- "Tümünü Seç" / "Tümünü Kaldır" butonlarını kullanın
- Bireysel sunucu onay kutuları belirli sunucuları etkinleştirir/devre dışı bırakır

### 4.2 Spectra MCP Sunucularını Kaldırma

Şu anda sunucu kaldırma manuel olarak yapılmalı:

1. Spectra yapılandırma dosyanızı açın
2. MCP sunucuları bölümünü bulun
3. İstenmeyen sunucu girdisini kaldırın
4. Spectra'yı yeniden başlatın

**Yapılandırma konumu:**
- **macOS/Linux:** `~/.spectra/config.json`
- **Windows:** `%USERPROFILE%\.spectra\config.json`

---

## 5. MCP Sunucu Yapılandırması

### 5.1 Dosya Sistemi Sunucu Örneği

**Sunucu Adı:** `filesystem-local`
**Komut:** `npx`
**Argümanlar:** `-y @modelcontextprotocol/server-filesystem`
**Ortam:** `ALLOWED_PATHS=/tmp,/home/user/projects,/Users/user/Masaüstü`

**Ne yapar:** Spectra'nın belirtilen dizinlerdeki dosyaları okumasını ve yazmasını sağlar.

### 5.2 PostgreSQL Sunucu Örneği

**Sunucu Adı:** `postgres-prod`
**Komut:** `uvx`
**Argümanlar:** `--from mcp-server-postgres mcp_server_postgres.server`
**Ortam:** `POSTGRES_CONNECTION_STRING=postgresql://user:pass@localhost:5432/dbname`

**Ne yapar:** Spectra'nın PostgreSQL veritabanlarını sorgulamasını sağlar.

### 5.3 Web Kazıyıcı Sunucu Örneği

**Sunucu Adı:** `web-fetcher`
**Komut:** `python`
**Argümanlar:** `-m mcp_server_web`
**Ortam:** `USER_AGENT=Spectra-Analysis/1.0`

**Ne yapar:** Spectra'nın analiz sırasında web içeriğini getirip analiz etmesini sağlar.

---

## 6. Popüler MCP Sunucuları

### 6.1 Resmi MCP Sunucuları

| Sunucu | Kurulum | Kullanım Durumu |
|--------|---------|----------------|
| **@modelcontextprotocol/server-filesystem** | Node.js ile yerleşik | Dosya sistemi işlemleri |
| **@modelcontextprotocol/server-github** | `npx @modelcontextprotocol/server-github` | GitHub deposu entegrasyonu |
| **@modelcontextprotocol/server-postgres** | `pip install mcp-server-postgres` | PostgreSQL veritabanı sorguları |
| **@modelcontextprotocol/server-puppeteer** | `npx @modelcontextprotocol/server-puppeteer` | Web otomasyonu ve kazıma |
| **@modelcontextprotocol/server-brave-search** | `npx @modelcontextprotocol/server-brave-search` | Web arama yetenekleri |

### 6.2 Topluluk MCP Sunucuları

- **mcp-server-sqlite** - SQLite veritabanı entegrasyonu
- **mcp-server-kubernetes** - Kubernetes küme yönetimi
- **mcp-server-aws** - AWS hizmeti entegrasyonu
- **mcp-server-git** - Git deposu işlemleri

---

## 7. Sorun Giderme

### 7.1 Sunucu Başlamıyor

**Sorun:** Eklenen MCP sunucusu araç listesinde görünmüyor

**Çözümler:**
1. Komutun sisteminizde kurulu olduğunu kontrol edin
2. Argümanların doğru biçimlendirildiğini doğrulayın
3. Ortam değişkenlerinin doğru ayarlandığını kontrol edin
4. Yavaş sunucular için zaman aşımı değerini artırın
5. Spectra günlüklerinde hata iletilerini kontrol edin

### 7.2 İzin Hataları

**Sorun:** Sunucu başlıyor ama kaynaklara erişemiyor

**Çözümler:**
1. Erişim kontrolü için ortam değişkenlerini kontrol edin
2. Dosya sistemi izinlerini doğrulayın
3. Veritabanı kimlik bilgilerinin doğru olduğunu kontrol edin
4. Uzak sunucular için ağ bağlantısını kontrol edin

### 7.3 Zaman Aşımı Sorunları

**Sorun:** Sunucu işlemler sırasında zaman aşımına uğruyor

**Çözümler:**
1. Sunucu yapılandırmasında zaman aşımı değerini artırın
2. Sunucu tarafı işlemleri optimize edin
3. Ağ gecikmesini kontrol edin
4. Sorgu karmaşıklığını azaltın

### 7.4 Claude Code/Codex Sunucuları Görünmüyor

**Sorun:** Harici MCP sunucuları algılanamıyor

**Çözümler:**
1. Claude Code/Codex'in doğru yapılandırıldığını doğrulayın
2. Bu araçlardaki MCP yapılandırmasını kontrol edin
3. Harici araçları yapılandırdıktan sonra Spectra'yı yeniden başlatın
4. MCP sunucularının kaynak araçta etkinleştirildiğinden emin olun

---

## 8. Güvenlik Hususları

### 8.1 Dosya Sistemi Erişimi

⚠️ **Uyarı:** Dosya sistemi erişimi olan MCP sunucuları hassas verileri okuyabilir/yazabilir

**En İyi Uygulamalar:**
- Erişimi kısıtlamak için her zaman `ALLOWED_PATHS` kullanın
- Asla sistem dizinlerine erişim izni vermeyin
- Özel proje dizinleri kullanın
- Sunucu izinlerini düzenli olarak gözden geçirin

### 8.2 Veritabanı Kimlik Bilgileri

⚠️ **Uyarı:** Veritabanı parolaları yapılandırmada saklanır

**En İyi Uygulamalar:**
- Mümkün olduğunda salt okunur veritabanı kullanıcıları kullanın
- Kimlik bilgilerini düzenli olarak döndürün
- Sabit kodlanmış değerler yerine ortam değişkenleri kullanın
- Sırlar yönetimi araçlarını kullanmayı düşünün

### 8.3 Ağ Erişimi

⚠️ **Uyarı:** MCP sunucuları ağ istekleri yapabilir

**En İyi Uygulamalar:**
- Kurulumdan önce sunucu kodunu gözden geçirin
- Erişimi kısıtlamak için güvenlik duvarları kullanın
- Ağ trafiğini izleyin
- Sadece güvenilir kaynaklardan yükleyin

### 8.4 Kod Yürütme

⚠️ **Uyarı:** Bazı MCP sunucuları rastgele kod yürütebilir

**En İyi Uygulamalar:**
- Sadece güvenilir kaynaklardan sunucu yükleyin
- Sunucu uygulamasını gözden geçirin
- Mümkün olduğunda sandbox edilmiş ortamlar kullanın
- Kullanılmadığında sunucuları devre dışı bırakın

---

## 9. Hızlı Referans

### 9.1 Yaygın Komutlar

```bash
# Node.js tabanlı MCP sunucusu kurulumu
npx -y @modelcontextprotocol/server-filesystem

# Python tabanlı MCP sunucusu kurulumu
pip install mcp-server-postgres

# UV tabanlı MCP sunucusu kurulumu
uvx mcp-server-postgres
```

### 9.2 Ortam Değişkeni Örnekleri

```bash
# Path kısıtlamaları olan dosya sunucusu
ALLOWED_PATHS=/home/user/projects,/tmp

# Veritabanı bağlantısı
POSTGRES_CONNECTION_STRING=postgresql://user:pass@localhost/db

# Özel yapılandırma
CUSTOM_VAR=value,BAŞKA_BİR_DEĞİŞKEN=value2
```

### 9.3 Yapılandırma Dosyası Formatı

```json
{
  "name": "sunucum",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem"],
  "env": {
    "ALLOWED_PATHS": "/tmp,/home/user"
  },
  "timeout": 30.0,
  "enabled": true
}
```

---

## 10. Yardım Alma

### 10.1 Kaynaklar

- **Resmi MCP Dokümantasyonu:** https://modelcontextprotocol.io
- **Spectra GitHub:** https://github.com/alicangnll/Spectra
- **MCP Sunucu Deposu:** https://github.com/modelcontextprotocol/servers

### 10.2 Topluluk Desteği

- **GitHub Issues:** Hata raporlayın ve özellik isteyin
- **Discussions:** Sorular sorun ve bilgi paylaşın
- **Pull Requests:** İyileştirmeler katkıda bulunun

---

## 11. Değişiklik Günlüğü

### Sürüm 1.0 (2025-08-15)
- İlk MCP sunucu kılavuzu
- Spectra, Claude Code ve Codex MCP kategorileri için destek
- Detaylı yapılandırma örnekleri
- Güvenlik en iyi uygulamaları

---

**Son Güncelleme:** 15 Ağustos 2026
