import type { BusinessLead } from "@/lib/types";

type Seed = Partial<BusinessLead> & Pick<BusinessLead, "business_name" | "city" | "industry" | "phone" | "address" | "rating" | "reviews_count" | "opportunity_score" | "pitch_angle">;

const seeds: Seed[] = [
  { business_name: "Bayou City Rooter", city: "Houston, TX", industry: "Plumbing", phone: "(713) 555-0184", address: "1919 N Loop W, Houston, TX 77008", rating: 4.9, reviews_count: 214, opportunity_score: 96, pitch_angle: "NO_WEBSITE", facebook: "https://facebook.com" },
  { business_name: "Lone Star Climate Co.", city: "Austin, TX", industry: "HVAC", phone: "(512) 555-0147", address: "4401 Freidrich Ln, Austin, TX 78744", rating: 4.8, reviews_count: 182, opportunity_score: 93, pitch_angle: "SOCIAL_ONLY", instagram: "https://instagram.com", facebook: "https://facebook.com" },
  { business_name: "Oakline Roofing", city: "Dallas, TX", industry: "Roofing", phone: "(214) 555-0192", address: "2727 Irving Blvd, Dallas, TX 75207", rating: 4.7, reviews_count: 326, opportunity_score: 89, pitch_angle: "REDESIGN_SSL", website_url: "http://oaklineroofing.example", cms_platform: "Wix", load_time_ms: 4800 },
  { business_name: "Coral Cut Landscaping", city: "Miami, FL", industry: "Landscaping", phone: "(305) 555-0119", address: "7280 NW 7th St, Miami, FL 33126", rating: 4.9, reviews_count: 97, opportunity_score: 91, pitch_angle: "NO_WEBSITE" },
  { business_name: "Peachtree Auto Spa", city: "Atlanta, GA", industry: "Auto Detailing", phone: "(404) 555-0156", address: "1130 Northside Dr NW, Atlanta, GA 30318", rating: 4.8, reviews_count: 159, opportunity_score: 87, pitch_angle: "SEO_ANALYTICS", website_url: "https://peachtreeautospa.example", has_ssl: true, is_mobile_friendly: true, cms_platform: "WordPress", email: "hello@peachtreeautospa.com", email_mx_valid: true, instagram: "https://instagram.com" },
  { business_name: "Copper Pipe Pros", city: "Austin, TX", industry: "Plumbing", phone: "(512) 555-0168", address: "9300 S I-35, Austin, TX 78748", rating: 4.6, reviews_count: 88, opportunity_score: 84, pitch_angle: "SOCIAL_ONLY", facebook: "https://facebook.com" },
  { business_name: "Sunbelt Air Works", city: "Houston, TX", industry: "HVAC", phone: "(281) 555-0135", address: "5800 Corporate Dr, Houston, TX 77036", rating: 4.5, reviews_count: 241, opportunity_score: 72, pitch_angle: "SEO_ANALYTICS", website_url: "https://sunbeltair.example", has_ssl: true, is_mobile_friendly: true, cms_platform: "Webflow", email: "service@sunbeltair.com", email_mx_valid: true, load_time_ms: 1800 },
  { business_name: "Metroplex Roof Lab", city: "Dallas, TX", industry: "Roofing", phone: "(972) 555-0177", address: "13601 Preston Rd, Dallas, TX 75240", rating: 4.8, reviews_count: 418, opportunity_score: 79, pitch_angle: "REDESIGN_SSL", website_url: "http://metroplexroof.example", cms_platform: "Wix", email: "quotes@metroplexroof.com", email_mx_valid: true, load_time_ms: 5100 },
  { business_name: "Palmera Outdoor Living", city: "Miami, FL", industry: "Landscaping", phone: "(786) 555-0122", address: "9425 SW 72nd St, Miami, FL 33173", rating: 4.7, reviews_count: 132, opportunity_score: 68, pitch_angle: "SEO_ANALYTICS", website_url: "https://palmera.example", has_ssl: true, is_mobile_friendly: true, cms_platform: "Squarespace", email: "hola@palmeraoutdoor.com", email_mx_valid: true, load_time_ms: 2300 },
  { business_name: "Midtown Mirror Finish", city: "Atlanta, GA", industry: "Auto Detailing", phone: "(678) 555-0140", address: "151 14th St NW, Atlanta, GA 30318", rating: 5, reviews_count: 64, opportunity_score: 94, pitch_angle: "NO_WEBSITE", instagram: "https://instagram.com" },
  { business_name: "Apex Flow Plumbing", city: "Dallas, TX", industry: "Plumbing", phone: "(469) 555-0181", address: "4849 Greenville Ave, Dallas, TX 75206", rating: 4.4, reviews_count: 73, opportunity_score: 58, pitch_angle: "ESTABLISHED", website_url: "https://apexflow.example", has_ssl: true, is_mobile_friendly: true, has_analytics: true, has_meta_pixel: true, cms_platform: "WordPress", email: "dispatch@apexflow.com", email_mx_valid: true, load_time_ms: 1400 },
  { business_name: "Atlantic Breeze HVAC", city: "Miami, FL", industry: "HVAC", phone: "(305) 555-0199", address: "8325 NW 64th St, Miami, FL 33166", rating: 4.6, reviews_count: 207, opportunity_score: 76, pitch_angle: "SEO_ANALYTICS", website_status: "WAF_PROTECTED", website_url: "https://atlanticbreeze.example", has_ssl: true, is_mobile_friendly: true, cms_platform: "Custom", email: "care@atlanticbreeze.com", email_mx_valid: true },
  { business_name: "Crownline Exteriors", city: "Atlanta, GA", industry: "Roofing", phone: "(770) 555-0108", address: "2800 Century Pkwy NE, Atlanta, GA 30345", rating: 4.7, reviews_count: 301, opportunity_score: 65, pitch_angle: "ESTABLISHED", website_url: "https://crownline.example", has_ssl: true, is_mobile_friendly: true, has_analytics: true, cms_platform: "Webflow", email: "team@crownline.com", email_mx_valid: true, linkedin: "https://linkedin.com", load_time_ms: 1200 },
  { business_name: "Verdant Edge Lawns", city: "Houston, TX", industry: "Landscaping", phone: "(832) 555-0161", address: "12620 FM 1960 W, Houston, TX 77065", rating: 4.3, reviews_count: 49, opportunity_score: 81, pitch_angle: "REDESIGN_SSL", website_status: "BROKEN", website_url: "http://verdantedge.example", cms_platform: "WordPress", email: "owner@verdantedge.com", email_mx_valid: false, load_time_ms: 7300 },
];

export const leads: BusinessLead[] = seeds.map((seed, index) => {
  const noSite = seed.pitch_angle === "NO_WEBSITE" || seed.pitch_angle === "SOCIAL_ONLY";
  return {
    id: `lead_${String(index + 1).padStart(3, "0")}`,
    is_franchise: false,
    website_status: noSite ? "NO_WEBSITE" : "LIVE",
    website_url: null,
    has_ssl: false,
    is_mobile_friendly: false,
    cms_platform: null,
    has_analytics: false,
    has_meta_pixel: false,
    load_time_ms: null,
    email: null,
    email_status: seed.email_mx_valid ? "VERIFIED" : "UNKNOWN",
    email_mx_valid: false,
    linkedin: null,
    instagram: null,
    facebook: null,
    twitter: null,
    pitch_tier: seed.opportunity_score >= 80 ? "HOT" : seed.opportunity_score >= 50 ? "WARM" : "COLD",
    pitch_summary: noSite
      ? "Strong local reputation but no owned web presence. A conversion-first site could capture high-intent search traffic now lost to directories."
      : "Established demand with clear technical gaps. A focused redesign and tracking layer can turn existing traffic into attributable leads.",
    outreach_status: index === 4 ? "REPLIED" : index === 7 ? "CONTACTED" : "NEW",
    outreach_notes: "",
    discovered_at: new Date(Date.now() - index * 43_200_000).toISOString(),
    ...seed,
  };
});
