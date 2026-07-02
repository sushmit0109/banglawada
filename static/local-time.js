(function () {
  const timeElements = document.querySelectorAll('[data-utc-time]');
  if (!timeElements.length) return;

  const TIMEZONE_COUNTRY_CODES = {
    'Africa/Cairo': 'EG',
    'Africa/Casablanca': 'MA',
    'Africa/Johannesburg': 'ZA',
    'Africa/Lagos': 'NG',
    'Africa/Nairobi': 'KE',
    'America/Argentina/Buenos_Aires': 'AR',
    'America/Bogota': 'CO',
    'America/Chicago': 'US',
    'America/Denver': 'US',
    'America/Detroit': 'US',
    'America/Edmonton': 'CA',
    'America/Halifax': 'CA',
    'America/Indiana/Indianapolis': 'US',
    'America/Los_Angeles': 'US',
    'America/Mexico_City': 'MX',
    'America/New_York': 'US',
    'America/Phoenix': 'US',
    'America/Santiago': 'CL',
    'America/Sao_Paulo': 'BR',
    'America/Toronto': 'CA',
    'America/Vancouver': 'CA',
    'Asia/Almaty': 'KZ',
    'Asia/Amman': 'JO',
    'Asia/Ashgabat': 'TM',
    'Asia/Baghdad': 'IQ',
    'Asia/Baku': 'AZ',
    'Asia/Bangkok': 'TH',
    'Asia/Beirut': 'LB',
    'Asia/Dhaka': 'BD',
    'Asia/Dubai': 'AE',
    'Asia/Ho_Chi_Minh': 'VN',
    'Asia/Hong_Kong': 'HK',
    'Asia/Jakarta': 'ID',
    'Asia/Jerusalem': 'IL',
    'Asia/Kabul': 'AF',
    'Asia/Karachi': 'PK',
    'Asia/Kathmandu': 'NP',
    'Asia/Kolkata': 'IN',
    'Asia/Kuala_Lumpur': 'MY',
    'Asia/Kuwait': 'KW',
    'Asia/Manila': 'PH',
    'Asia/Muscat': 'OM',
    'Asia/Qatar': 'QA',
    'Asia/Riyadh': 'SA',
    'Asia/Seoul': 'KR',
    'Asia/Shanghai': 'CN',
    'Asia/Singapore': 'SG',
    'Asia/Taipei': 'TW',
    'Asia/Tashkent': 'UZ',
    'Asia/Tehran': 'IR',
    'Asia/Tokyo': 'JP',
    'Australia/Adelaide': 'AU',
    'Australia/Brisbane': 'AU',
    'Australia/Melbourne': 'AU',
    'Australia/Perth': 'AU',
    'Australia/Sydney': 'AU',
    'Europe/Amsterdam': 'NL',
    'Europe/Athens': 'GR',
    'Europe/Berlin': 'DE',
    'Europe/Brussels': 'BE',
    'Europe/Bucharest': 'RO',
    'Europe/Budapest': 'HU',
    'Europe/Copenhagen': 'DK',
    'Europe/Dublin': 'IE',
    'Europe/Helsinki': 'FI',
    'Europe/Istanbul': 'TR',
    'Europe/Lisbon': 'PT',
    'Europe/London': 'GB',
    'Europe/Madrid': 'ES',
    'Europe/Moscow': 'RU',
    'Europe/Oslo': 'NO',
    'Europe/Paris': 'FR',
    'Europe/Prague': 'CZ',
    'Europe/Rome': 'IT',
    'Europe/Stockholm': 'SE',
    'Europe/Vienna': 'AT',
    'Europe/Warsaw': 'PL',
    'Europe/Zurich': 'CH',
    'Pacific/Auckland': 'NZ',
  };

  const countryNames = typeof Intl.DisplayNames === 'function'
    ? new Intl.DisplayNames(['bn-BD'], { type: 'region' })
    : null;

  const getBrowserCountryName = () => {
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const countryCode = TIMEZONE_COUNTRY_CODES[timezone];
    if (!countryCode || !countryNames) return '';
    return countryNames.of(countryCode) || '';
  };

  const formatLocalTime = (isoTime) => {
    const date = new Date(isoTime);
    if (Number.isNaN(date.getTime())) return '';

    const datePart = new Intl.DateTimeFormat('bn-BD', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    }).format(date);

    const timePart = new Intl.DateTimeFormat('bn-BD', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(date);

    const countryName = getBrowserCountryName();

    return `${datePart}, ${timePart}${countryName ? ` ${countryName}` : ''}`;
  };

  timeElements.forEach((element) => {
    const localTime = formatLocalTime(element.dataset.utcTime);
    if (localTime) {
      element.textContent = localTime;
      element.title = 'আপনার ব্রাউজারের স্থানীয় সময় অনুযায়ী';
    }
  });
}());
