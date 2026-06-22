"use client";

import { useState, useRef, useEffect, FormEvent } from "react";
import { ChartRequest, ChartResponse } from "@/types/chart";
import { fetchChart, APIError } from "@/services/api";
import { LABELS, ERROR_MESSAGES, PLACEHOLDERS } from "@/utils/constants";

interface PhotonFeature {
  properties: {
    name: string;
    state?: string;
    country?: string;
    countrycode?: string;
    osm_key?: string;
  };
  geometry: {
    coordinates: [number, number]; // [lng, lat]
  };
}

interface ChartFormProps {
  onSuccess: (data: ChartResponse) => void;
  onError: (error: string) => void;
}

export default function ChartForm({ onSuccess, onError }: ChartFormProps) {
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState<ChartRequest>({
    firstName: "",
    birthDate: "",
    birthTime: "",
    birthTimeApproximate: false,
    birthPlace: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const [suggestions, setSuggestions] = useState<PhotonFeature[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [placeCoords, setPlaceCoords] = useState<{ lat: number; lng: number } | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const fetchSuggestions = async (query: string) => {
    try {
      const res = await fetch(
        `https://photon.komoot.io/api/?q=${encodeURIComponent(query)}&limit=8&lang=de`
      );
      const data = await res.json();
      const places = (data.features as PhotonFeature[]).filter(
        (f) => f.properties.osm_key === "place"
      );
      setSuggestions(places.slice(0, 5));
      setShowSuggestions(places.length > 0);
    } catch {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  };

  const clearPlaceError = () => {
    if (errors.birthPlace) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next.birthPlace;
        return next;
      });
    }
  };

  const handlePlaceChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setFormData((prev) => ({ ...prev, birthPlace: value }));
    setPlaceCoords(null);
    clearPlaceError();

    clearTimeout(debounceRef.current);
    if (value.length >= 2) {
      debounceRef.current = setTimeout(() => fetchSuggestions(value), 300);
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  };

  const handleSelectSuggestion = (feature: PhotonFeature) => {
    const { name, state, country } = feature.properties;
    const label = [name, state, country].filter(Boolean).join(", ");
    const [lng, lat] = feature.geometry.coordinates;

    setFormData((prev) => ({ ...prev, birthPlace: label }));
    setPlaceCoords({ lat, lng });
    setSuggestions([]);
    setShowSuggestions(false);
    clearPlaceError();
  };

  const validateField = (name: string, value: string): string | null => {
    switch (name) {
      case "firstName":
        if (!value || value.length < 2) return ERROR_MESSAGES.invalidName;
        break;
      case "birthDate":
        if (!/^\d{2}\.\d{2}\.\d{4}$/.test(value)) return ERROR_MESSAGES.invalidDate;
        break;
      case "birthTime":
        if (!formData.birthTimeApproximate && !/^\d{2}:\d{2}$/.test(value))
          return ERROR_MESSAGES.invalidTime;
        break;
      case "birthPlace":
        if (!value || value.length < 2) return ERROR_MESSAGES.required;
        break;
    }
    return null;
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    const newValue = type === "checkbox" ? checked : value;

    setFormData((prev) => ({ ...prev, [name]: newValue }));

    if (errors[name]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    onError("");

    const newErrors: Record<string, string> = {};
    Object.entries(formData).forEach(([key, value]) => {
      if (key !== "birthTimeApproximate") {
        const error = validateField(key, value as string);
        if (error) newErrors[key] = error;
      }
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      setLoading(false);
      return;
    }

    try {
      const requestData: ChartRequest = {
        ...formData,
        birthTime:
          formData.birthTimeApproximate && !formData.birthTime
            ? "12:00"
            : formData.birthTime,
        ...(placeCoords
          ? { latitude: placeCoords.lat, longitude: placeCoords.lng }
          : {}),
      };

      const result = await fetchChart(requestData);
      onSuccess(result);
    } catch (error) {
      if (error instanceof APIError) {
        if (error.field) {
          setErrors({ [error.field]: error.message });
        } else {
          onError(error.message);
        }
      } else {
        onError(ERROR_MESSAGES.unexpectedError);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 bg-white p-8 rounded-lg shadow-md">
      <div>
        <label htmlFor="firstName" className="block text-sm font-medium text-primary mb-2">
          {LABELS.firstName}
        </label>
        <input
          type="text"
          id="firstName"
          name="firstName"
          value={formData.firstName}
          onChange={handleChange}
          placeholder={PLACEHOLDERS.firstName}
          className={`w-full px-4 py-2 border rounded-md focus:outline-none focus:ring-2 ${
            errors.firstName
              ? "border-error focus:ring-error"
              : "border-secondary focus:ring-accent"
          }`}
          required
        />
        {errors.firstName && (
          <p className="mt-1 text-sm text-error">{errors.firstName}</p>
        )}
      </div>

      <div>
        <label htmlFor="birthDate" className="block text-sm font-medium text-primary mb-2">
          {LABELS.birthDate}
        </label>
        <input
          type="text"
          id="birthDate"
          name="birthDate"
          value={formData.birthDate}
          onChange={handleChange}
          placeholder={PLACEHOLDERS.birthDate}
          className={`w-full px-4 py-2 border rounded-md focus:outline-none focus:ring-2 ${
            errors.birthDate
              ? "border-error focus:ring-error"
              : "border-secondary focus:ring-accent"
          }`}
          required
        />
        {errors.birthDate && (
          <p className="mt-1 text-sm text-error">{errors.birthDate}</p>
        )}
        <p className="mt-1 text-xs text-secondary">Format: TT.MM.JJJJ</p>
      </div>

      <div>
        <label htmlFor="birthTime" className="block text-sm font-medium text-primary mb-2">
          {LABELS.birthTime}
        </label>
        <input
          type="text"
          id="birthTime"
          name="birthTime"
          value={formData.birthTime}
          onChange={handleChange}
          placeholder={PLACEHOLDERS.birthTime}
          disabled={formData.birthTimeApproximate}
          className={`w-full px-4 py-2 border rounded-md focus:outline-none focus:ring-2 ${
            errors.birthTime
              ? "border-error focus:ring-error"
              : "border-secondary focus:ring-accent"
          } ${formData.birthTimeApproximate ? "bg-gray-100" : ""}`}
          required={!formData.birthTimeApproximate}
        />
        {errors.birthTime && (
          <p className="mt-1 text-sm text-error">{errors.birthTime}</p>
        )}
        <p className="mt-1 text-xs text-secondary">Format: HH:MM</p>

        <div className="mt-2">
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              name="birthTimeApproximate"
              checked={formData.birthTimeApproximate}
              onChange={handleChange}
              className="w-4 h-4 text-accent border-secondary rounded focus:ring-accent"
            />
            <span className="text-sm text-secondary">{LABELS.birthTimeApproximate}</span>
          </label>
        </div>
      </div>

      <div>
        <label htmlFor="birthPlace" className="block text-sm font-medium text-primary mb-2">
          {LABELS.birthPlace}
        </label>
        <div className="relative" ref={containerRef}>
          <input
            type="text"
            id="birthPlace"
            name="birthPlace"
            value={formData.birthPlace}
            onChange={handlePlaceChange}
            placeholder={PLACEHOLDERS.birthPlace}
            autoComplete="off"
            className={`w-full px-4 py-2 border rounded-md focus:outline-none focus:ring-2 ${
              errors.birthPlace
                ? "border-error focus:ring-error"
                : "border-secondary focus:ring-accent"
            }`}
            required
          />
          {showSuggestions && suggestions.length > 0 && (
            <ul className="absolute z-10 w-full mt-1 bg-white border border-secondary rounded-md shadow-lg max-h-60 overflow-auto">
              {suggestions.map((feature, i) => {
                const { name, state, country } = feature.properties;
                const label = [name, state, country].filter(Boolean).join(", ");
                return (
                  <li
                    key={i}
                    onMouseDown={() => handleSelectSuggestion(feature)}
                    className="px-4 py-2 cursor-pointer hover:bg-gray-100 text-sm text-primary border-b border-gray-100 last:border-0"
                  >
                    {label}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        {errors.birthPlace && (
          <p className="mt-1 text-sm text-error">{errors.birthPlace}</p>
        )}
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full bg-primary text-white py-3 px-6 rounded-md font-medium hover:bg-opacity-90 focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? "Generiere..." : LABELS.generateChart}
      </button>
    </form>
  );
}
