import type { ExportProfile } from "@/lib/api/schema";

export const EXPORT_PROFILE_STORAGE_KEY = "barum-us-export-profile";

export const DEFAULT_EXPORT_PROFILE: ExportProfile = {
  legal_manufacturer: "",
  manufacturer_name: "",
  manufacturing_site: "",
  manufacturing_site_address: "",
  us_agent_name: "",
  us_agent_contact: "",
  importer_name: "",
  importer_contact: "",
  fda_establishment_registration: "",
  fda_establishment_registration_number: "",
  registration_status: "",
  registration_renewal_date: "",
  cgmp_ready: null,
  drug_listing_status: "",
  ndc_or_listing_number: "",
};

export function readExportProfile(): ExportProfile {
  if (typeof window === "undefined") return DEFAULT_EXPORT_PROFILE;
  try {
    const raw = window.localStorage.getItem(EXPORT_PROFILE_STORAGE_KEY);
    if (!raw) return DEFAULT_EXPORT_PROFILE;
    const parsed = JSON.parse(raw);
    return { ...DEFAULT_EXPORT_PROFILE, ...(parsed && typeof parsed === "object" ? parsed : {}) };
  } catch {
    return DEFAULT_EXPORT_PROFILE;
  }
}

export function writeExportProfile(profile: ExportProfile): void {
  window.localStorage.setItem(EXPORT_PROFILE_STORAGE_KEY, JSON.stringify(profile));
}
