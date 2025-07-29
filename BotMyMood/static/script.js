document.addEventListener("DOMContentLoaded", () => {
  const checkBtn = document.getElementById("check-btn");
  const disconnectBtn = document.getElementById("disconnect-btn");
  const apiInput = document.getElementById("apikey");
  const form = document.getElementById("main-form");
  const loading = document.getElementById("loading");
  const errorMessageDiv = document.getElementById("error-message"); // Hata mesajı div'i

  // Sayfa yüklendiğinde bağlantı durumunu kontrol et ve input'u ayarla
  // `connected` durumu Jinja2 tarafından belirlenir ve buna göre sınıflandırma yapılır.
  const isInitiallyConnected = checkBtn.classList.contains("connected");
  if (isInitiallyConnected) {
    apiInput.readOnly = true;
    apiInput.type = "password";
    apiInput.value = "********************"; // Maskeleme için sabit bir değer
  }

  // Hata mesajını gösterme fonksiyonu
  function showError(message) {
    errorMessageDiv.textContent = message;
    errorMessageDiv.classList.remove("hidden");
    errorMessageDiv.classList.add("error-box"); 
  }

  // Hata mesajını gizleme fonksiyonu
  function hideError() {
    errorMessageDiv.classList.add("hidden");
    errorMessageDiv.textContent = "";
    errorMessageDiv.classList.remove("error-box");
  }

  // API doğrulama isteğini sunucuya gönderme
  async function validateKeyOnServer(key) {
    try {
      const response = await fetch("/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apikey: key })
      });
      const result = await response.json();
      return result; // { ok: boolean, error?: string, masked?: string }
    } catch (error) {
      console.error("Sunucuya bağlanırken hata oluştu:", error);
      return { ok: false, error: "Sunucuya ulaşılamadı. Lütfen ağ bağlantınızı kontrol edin." };
    }
  }

  // Bağla butonu tıklama olayı
  checkBtn.addEventListener("click", async () => {
    const key = apiInput.value.trim();

    if (key.length < 15) { // Minimum API anahtarı uzunluğu kontrolü
      showError("Lütfen geçerli uzunlukta bir API anahtarı girin.");
      return;
    }

    checkBtn.textContent = "Doğrulanıyor...";
    checkBtn.disabled = true;
    hideError(); // Önceki hataları temizle

    const validationResult = await validateKeyOnServer(key);

    if (validationResult.ok) {
      checkBtn.classList.add("connected");
      checkBtn.textContent = "Bağlı";
      apiInput.readOnly = true; // Giriş alanını kilitler
      apiInput.type = "password"; // Alanı parola tipine çevirir
      apiInput.value = validationResult.masked || "********************"; // Maskelenmiş değeri kullan
      alert(validationResult.message || "API anahtarı başarıyla bağlandı!");
    } else {
      showError(validationResult.error || "API anahtarı geçersiz. Lütfen doğru anahtarı girdiğinizden emin olun.");
      apiInput.value = ""; // Geçersiz anahtarı temizle
    }

    checkBtn.disabled = false;
  });

  // Bağlantıyı kes butonu tıklama olayı
  disconnectBtn.addEventListener("click", () => {
    // Bu işlem sadece istemci tarafında bağlantı durumunu sıfırlar.
    // Gerçek bir uygulamada, sunucu tarafında da bağlı anahtarı silmek için
    // ayrı bir endpoint (örneğin /disconnect) çağrısı yapmak daha güvenli olurdu.
    checkBtn.classList.remove("connected");
    checkBtn.textContent = "Bağla";
    checkBtn.disabled = false;
    apiInput.readOnly = false; // Giriş alanını tekrar düzenlenebilir yapar
    apiInput.type = "text"; // Alanı metin tipine çevirir
    apiInput.value = ""; // Anahtar değerini temizler
    hideError(); // Hata mesajını temizle
    alert("API bağlantısı kesildi. Yeniden bağlanmak için anahtarınızı girin.");
  });

  // Form gönderim olayı
  form.addEventListener("submit", (e) => {
    // Eğer API anahtarı alanı boş veya maskeli değerdeyse ve "Bağlı" sınıfı yoksa
    if ((!apiInput.value || apiInput.value === "********************") && !checkBtn.classList.contains("connected")) { 
        e.preventDefault(); // Formu göndermeyi durdur
        showError("Lütfen önce geçerli bir API anahtarını bağlayın.");
        return;
    }
    hideError(); // Gönderim öncesi hataları temizle
    loading.classList.remove("hidden"); // Yükleniyor mesajını göster
  });

  // Sayfa yüklendiğinde, eğer Jinja tarafından bir hata mesajı render edilmişse onu göster
  // Bu, özellikle /analyze POST isteğinden sonra gelen hatalar için geçerlidir.
  const initialErrorMessage = errorMessageDiv.textContent.trim();
  if (initialErrorMessage !== "") {
    showError(initialErrorMessage);
  }
});