from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import google.generativeai as genai
import logging
import os # Ortam değişkenlerini kullanmak için (ileride API anahtarını doğrudan kodda tutmak yerine kullanmak için)

app = FastAPI()

# Statik dosyaların (CSS, JS) bulunduğu klasörü belirt
app.mount("/static", StaticFiles(directory="static"), name="static")
# HTML şablonlarının bulunduğu klasörü belirt
templates = Jinja2Templates(directory="templates")

# Desteklenen sosyal medya platformları listesi
platforms = [
    "Instagram", "Twitter", "Facebook", "YouTube",
    "TikTok", "Snapchat", "Reddit", "Discord"
]

# API anahtarının sunucu tarafında geçici olarak tutulması için global değişken
# Bu değişken, uygulama çalıştığı sürece bağlı API anahtarını saklar.
# Bir server'a dağıtmayacağınız için bu yöntem yerel kullanım için uygun olabilir.
connected_api_key = None

class KeyPayload(BaseModel):
    # API anahtarını alacak Pydantic modeli
    apikey: str

@app.post("/validate")
async def validate_key(payload: KeyPayload):
    """
    API anahtarını Google Generative AI servisine bir test isteği göndererek doğrular.
    Tüm API etkileşimleri sunucu tarafında yapılır.
    """
    global connected_api_key # Global değişkeni kullanmak için
    try:
        # Gemini API'sini gelen anahtarla yapılandır
        genai.configure(api_key=payload.apikey)
        # En stabil ve yaygın olarak erişilebilir model: gemini-1.5-flash
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Basit bir içerik oluşturma testi yaparak anahtarı doğrula
        _ = model.generate_content("Merhaba, test mesajı.")
        
        # Doğrulama başarılı olursa anahtarı geçici olarak sakla
        connected_api_key = payload.apikey
        # İstemciye başarılı yanıt ve maskelenmiş anahtar döndür
        return {"ok": True, "masked": "*" * 20, "message": "API anahtarı başarıyla bağlandı!"} 
    except Exception as e:
        # Doğrulama sırasında bir hata oluşursa logla ve istemciye hata mesajı döndür
        logging.exception("API key validation failed:")
        error_detail = str(e)
        if "API_KEY_INVALID" in error_detail or "API key not valid" in error_detail:
            error_message = "API anahtarınız geçersiz veya eksik. Lütfen doğru anahtarı girdiğinizden emin olun."
        elif "PERMISSION_DENIED" in error_detail:
            error_message = "API anahtarınızın bu modeli kullanma izni olmayabilir. Google AI Studio ayarlarınızı kontrol edin."
        elif "RESOURCE_EXHAUSTED" in error_detail:
            error_message = "API kullanım limitlerinizi aşmış olabilirsiniz. Lütfen daha sonra tekrar deneyin."
        else:
            error_message = f"API doğrulama sırasında beklenmeyen bir hata oluştu: {error_detail}"
        return JSONResponse(status_code=400, content={"ok": False, "error": error_message})

@app.get("/", response_class=HTMLResponse)
async def form_get(request: Request):
    """
    Ana sayfayı (HTML formu) döndürür. Sayfa yüklendiğinde bağlantı durumunu kontrol eder.
    """
    global connected_api_key # Global değişkeni kullanmak için
    return templates.TemplateResponse("index.html", {
        "request": request,
        "platforms": platforms,
        # API anahtarının bağlı olup olmadığını istemciye bildir
        "connected": bool(connected_api_key),
        # Eğer bağlıysa maskeli anahtar gönder, değilse boş string
        "apikey": "*" * 20 if connected_api_key else "", 
        "username": "", # İlk yüklemede kullanıcı adını boş gönder
        "result": None, # İlk yüklemede sonuç yok
        "error_message": None # İlk yüklemede hata mesajı yok
    })

@app.post("/analyze", response_class=HTMLResponse)
async def analyze_post(
    request: Request,
    apikey: str = Form(...), # Formdan gelen API anahtarı
    username: str = Form(...) # Formdan gelen kullanıcı adı
):
    """
    Kullanıcının sosyal medya kullanım verilerini alır, AI analizi yapar ve sonucu döndürür.
    """
    global connected_api_key # Global değişkeni kullanmak için
    form_data = await request.form()
    # Sadece platformlara ait ve değeri olan girdileri al
    usage_dict = {key: value for key, value in form_data.items() if key in platforms and value}

    result = ""
    error_message = None

    try:
        # Her analiz isteği için API'yi gelen anahtarla yeniden yapılandır
        # Eğer connected_api_key varsa onu kullan, yoksa formdan geleni (ki bu validate edilmiş olmalı)
        current_api_key = connected_api_key if connected_api_key else apikey
        genai.configure(api_key=current_api_key)
        
        # Analiz için aynı modeli kullan: gemini-1.5-flash
        model = genai.GenerativeModel("models/gemini-1.5-flash")

        # Sosyal medya kullanım verilerini okunabilir metne dönüştür
        usage_text = "\n".join([f"{platform}: {hours} saat" for platform, hours in usage_dict.items()])
        # Toplam süreyi hesapla
        total_time = sum(float(h) for h in usage_dict.values()) if usage_dict else 0.0

        # AI modeline gönderilecek istemci (prompt)
        prompt = (
            f"Kullanıcının adı: {username}\n"
            f"Günlük sosyal medya kullanımı:\n{usage_text or 'veri girilmedi'}\n"
            f"Toplam süre: {total_time} saat\n\n"
            "Yukarıdaki verilere göre bu kişi hakkında detaylı, özgün ve kişisel bir ruhsal analiz yap. "
            "Cevap en az 3 paragraflık olsun; günlük yaşam kalitesi, dikkat/odak, uyku, sosyal ilişkiler ve dijital dengeyi değerlendir. "
            "Genel uyarılar (\"yeterli veri yok\" vb.) verme. Girdi değiştikçe anlamlı şekilde farklılaşan net ve uygulanabilir öneriler ver."
        )

        # AI modelinden yanıt al
        response = model.generate_content(prompt)
        result = response.text.strip()

    except Exception as e:
        # AI bağlantısı veya analiz sırasında oluşan hataları logla
        logging.exception("AI bağlantı hatası:")
        error_detail = str(e)
        if "API_KEY_INVALID" in error_detail or "API key not valid" in error_detail:
            error_message = "API anahtarınız geçersiz veya eksik. Lütfen doğru anahtarı girdiğinizden emin olun."
        elif "Model not found" in error_detail or "invalid model name" in error_detail:
            error_message = "Belirtilen yapay zeka modeli bulunamadı veya geçersiz. Lütfen kullandığınız model adını kontrol edin (örn: 'gemini-1.5-flash')."
        elif "RESOURCE_EXHAUSTED" in error_detail:
            error_message = "API kullanım limitlerinizi aşmış olabilirsiniz. Lütfen daha sonra tekrar deneyin veya farklı bir anahtar kullanın."
        elif "PERMISSION_DENIED" in error_detail:
            error_message = "API anahtarınızın bu modeli kullanma izni olmayabilir. Lütfen Google AI Studio'daki API anahtarı ayarlarınızı kontrol edin."
        else:
            error_message = f"Yapay zeka analizi sırasında beklenmeyen bir hata oluştu: {error_detail}"

    # Sonucu veya hata mesajını HTML şablonuna gönder
    return templates.TemplateResponse("index.html", {
        "request": request,
        "platforms": platforms,
        "result": result if not error_message else None, # Hata varsa sonucu gösterme
        "error_message": error_message, # Hata mesajını gönder
        # API anahtarını her zaman maskeli gönder, connected_api_key varsa onu kontrol et
        "apikey": "*" * 20 if connected_api_key else "", 
        "username": username,
        "connected": bool(connected_api_key) # Bağlantı durumunu gönder
    })