// Configuración de i18next
i18next
  .use(i18nextHttpBackend)
  .use(i18nextBrowserLanguageDetector)
  .init({
    fallbackLng: 'es',
    debug: false,
    backend: {
      loadPath: '/static/locales/{{lng}}/translation.json'
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage']
    }
  }, function(err, t) {
    if (err) console.error('i18next error:', err);
    updatePageLanguage();
  });

// Función para actualizar el idioma en la página
function updatePageLanguage() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const text = i18next.t(key);
    
    // Si es un input, usar placeholder; si es un button/label, usar textContent
    if (el.tagName === 'INPUT' && el.type !== 'hidden') {
      el.placeholder = text;
    } else if (el.tagName === 'LABEL' || el.tagName === 'BUTTON' || el.tagName === 'A') {
      el.textContent = text;
    } else {
      el.innerHTML = text;
    }
  });
}

// Función para cambiar idioma
function changeLanguage(lang) {
  i18next.changeLanguage(lang, (err, t) => {
    if (err) console.error('Error changing language:', err);
    updatePageLanguage();
    localStorage.setItem('lang', lang);
  });
}

// Obtener idioma actual
function getCurrentLanguage() {
  return i18next.language;
}
