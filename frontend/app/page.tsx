import { fetchProducts } from "@/lib/api";

import { Catalog } from "./catalog";

export const dynamic = "force-dynamic";

export default async function CatalogPage() {
  const products = await fetchProducts();

  return (
    <main>
      <Catalog initial={products} />
    </main>
  );
}
