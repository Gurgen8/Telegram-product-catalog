export type Product = {
  id: number;
  title: string;
  description: string | null;
  image_url: string;
  created_at: string;
};

type ProductPage = {
  items: Product[];
  total: number;
};

// Used for server-side rendering; the browser talks to the same API through nginx (see catalog.tsx).
const API_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

export async function fetchProducts(): Promise<Product[]> {
  const res = await fetch(`${API_URL}/api/products?limit=100`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Catalog API responded with ${res.status}`);
  }
  const page: ProductPage = await res.json();
  return page.items;
}
