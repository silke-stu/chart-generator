/**
 * German language constants and translations
 */

export const LABELS = {
  // Form labels
  firstName: "Vorname",
  birthDate: "Geburtsdatum",
  birthTime: "Geburtszeit",
  birthPlace: "Geburtsort",
  birthTimeApproximate: "Geburtszeit ungefähr / unbekannt",
  generateChart: "Chart Generieren",

  // Section titles
  yourType: "Dein Human Design Typ",
  yourAuthority: "Deine innere Autorität",
  yourProfile: "Dein Profil",
  yourCenters: "Deine Zentren",
  activeChannels: "Aktive Kanäle",
  activeGates: "Aktive Tore",
  yourIncarnationCross: "Dein Inkarnationskreuz",
  yourImpulse: "Ein Satz für dich",
  bodygraph: "Dein Bodygraph",

  // Center labels
  defined: "Definiert",
  open: "Offen",
  unconsciouslyDefined: "Unbewusst definiert",

  // Gate labels
  conscious: "Bewusst",
  unconscious: "Unbewusst",

  // Email capture
  emailCapture: "Interesse an Business Reading?",
  emailPlaceholder: "deine@email.de",
  submitEmail: "Absenden",

  // Actions
  retry: "Erneut versuchen",
  newChart: "Neues Chart",
};

export const ERROR_MESSAGES = {
  // Validation errors
  invalidDate: "Ungültiges Datumsformat. Bitte verwenden Sie TT.MM.JJJJ.",
  invalidTime: "Ungültiges Zeitformat. Bitte verwenden Sie HH:MM.",
  invalidName: "Bitte geben Sie einen gültigen Namen ein (2-50 Zeichen).",
  invalidEmail: "Ungültige E-Mail-Adresse. Bitte prüfen Sie Ihre Eingabe.",
  required: "Dieses Feld ist erforderlich.",

  // API errors
  apiUnavailable: "Gerade kann dein Chart nicht berechnet werden. Bitte versuche es später noch einmal.",
  unexpectedError: "Ein unerwarteter Fehler ist aufgetreten. Bitte versuche es später noch einmal.",
};

export const PLACEHOLDERS = {
  firstName: "Marie",
  birthDate: "23.11.1992",
  birthTime: "14:30",
  birthPlace: "Berlin, Germany",
};
