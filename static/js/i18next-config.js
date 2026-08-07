// Configuración de i18next con carga local robusta
(function () {
  const defaultLang = 'es';

  async function loadTranslations(lang) {
    const response = await fetch(`/static/locales/${lang}/translation.json`, { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`No se pudo cargar el idioma ${lang}`);
    }
    return response.json();
  }

  async function initI18n() {
    const savedLang = localStorage.getItem('lang') || defaultLang;

    try {
      const translations = await loadTranslations(savedLang);
      i18next.init({
        lng: savedLang,
        fallbackLng: defaultLang,
        debug: false,
        resources: {
          [savedLang]: { translation: translations }
        }
      });
    } catch (err) {
      console.error('i18next error:', err);
      i18next.init({
        lng: defaultLang,
        fallbackLng: defaultLang,
        debug: false,
        resources: {
          [defaultLang]: { translation: {} }
        }
      });
    }

    i18next.on('languageChanged', updatePageLanguage);
    updatePageLanguage();
  }

  function updatePageLanguage() {
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.getAttribute('data-i18n');
      const text = i18next.t(key);

      if (el.tagName === 'INPUT' && el.type !== 'hidden') {
        el.placeholder = text;
      } else if (el.tagName === 'LABEL' || el.tagName === 'BUTTON' || el.tagName === 'A') {
        el.textContent = text;
      } else {
        el.innerHTML = text;
      }
    });

    document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
      const key = el.getAttribute('data-i18n-placeholder');
      const text = i18next.t(key);
      if (text) {
        el.placeholder = text;
      }
    });
  }

  window.changeLanguage = function changeLanguage(lang) {
    localStorage.setItem('lang', lang);
    i18next.changeLanguage(lang, () => {
      updatePageLanguage();
    });
  };

  window.getCurrentLanguage = function getCurrentLanguage() {
    return i18next.language;
  };

  document.addEventListener('DOMContentLoaded', () => {
    initI18n();
  });
})();
