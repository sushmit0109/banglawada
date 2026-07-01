(function () {
  'use strict';

  const widget = document.getElementById('local-weather');
  if (!widget) return;

  const icons = {
    0: '☀️', 1: '🌤️', 2: '⛅', 3: '☁️', 45: '🌫️', 48: '🌫️',
    51: '🌦️', 53: '🌦️', 55: '🌧️', 56: '🌧️', 57: '🌧️',
    61: '🌧️', 63: '🌧️', 65: '🌧️', 66: '🌧️', 67: '🌧️',
    71: '🌨️', 73: '🌨️', 75: '❄️', 77: '❄️',
    80: '🌦️', 81: '🌧️', 82: '⛈️', 85: '🌨️', 86: '🌨️',
    95: '⛈️', 96: '⛈️', 99: '⛈️'
  };

  function showWeather(data) {
    document.getElementById('weather-icon').textContent = icons[data.code] || '🌡️';
    document.getElementById('weather-temperature').textContent = Math.round(data.temperature) + '°C';
    document.getElementById('weather-location').textContent = data.city;
    widget.hidden = false;
  }

  async function loadWeather() {
    try {
      const cacheKey = 'localWeatherIpCityBn';
      const cached = JSON.parse(localStorage.getItem(cacheKey) || 'null');
      if (cached && Date.now() - cached.savedAt < 15 * 60 * 1000) {
        showWeather(cached);
        return;
      }

      const locationResponse = await fetch('https://ipwho.is/');
      if (!locationResponse.ok) throw new Error('IP location lookup failed');
      const location = await locationResponse.json();
      if (!location.success || location.latitude == null || location.longitude == null) {
        throw new Error('IP location unavailable');
      }
      const latitude = location.latitude;
      const longitude = location.longitude;

      // Resolve the visitor's IP coordinates to a nearby city localized in Bengali.
      const cityParams = new URLSearchParams({
        lat: latitude,
        lon: longitude,
        format: 'jsonv2',
        zoom: '10',
        addressdetails: '1',
        'accept-language': 'bn'
      });
      const cityResponse = await fetch('https://nominatim.openstreetmap.org/reverse?' + cityParams);
      if (!cityResponse.ok) throw new Error('City lookup failed');
      const cityData = await cityResponse.json();
      const address = cityData.address || {};
      const city = address.city || address.town || address.municipality || address.village;
      if (!city) throw new Error('City unavailable');

      const params = new URLSearchParams({
        latitude: latitude,
        longitude: longitude,
        current: 'temperature_2m,weather_code',
        timezone: 'auto'
      });
      const weatherResponse = await fetch('https://api.open-meteo.com/v1/forecast?' + params);
      if (!weatherResponse.ok) throw new Error('Weather lookup failed');
      const weather = await weatherResponse.json();
      if (!weather.current) throw new Error('Weather unavailable');

      const result = {
        temperature: weather.current.temperature_2m,
        code: weather.current.weather_code,
        city: city,
        savedAt: Date.now()
      };
      localStorage.setItem(cacheKey, JSON.stringify(result));
      showWeather(result);
    } catch (error) {
      console.warn('Local weather could not be loaded:', error.message);
    }
  }

  loadWeather();
}());
