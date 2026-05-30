declare module "@/data/listings.json" {
  export interface Listing {
    title: string;
    company: string;
    location: string;
    source_site: string;
    remote: string;
    experience_level: string;
    languages: string[];
    skills: string[];
    posted_date: string;
    apply_url: string;
    description_summary: string;
    score: number;
    flags: string[];
    tier: "strong" | "consider" | "low" | string;
  }
  const data: { file: string; listings: Listing[] };
  export default data;
}