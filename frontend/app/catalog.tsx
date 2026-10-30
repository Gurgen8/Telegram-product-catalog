"use client";

import { useEffect, useState } from "react";

import type { Product } from "@/lib/api";

const LIST_URL = "/api/products?limit=100";
const WS_PATH = "/api/products/ws";
const RECONNECT_DELAY_MS = 2000;

type LiveMessage =
  | { type: "product"; product: Product }
  | { type: "deleted"; ids: number[] }
  | { type: "resync" }
  | { type: "ping" };

const dateFormat = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" });

function productsWord(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "товар";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "товара";
  return "товаров";
}

// Server renders the initial list; new products arrive over a WebSocket without a page reload.
export function Catalog({ initial }: { initial: Product[] }) {
  const [products, setProducts] = useState(initial);

  useEffect(() => {
    let cancelled = false;

    // Reload the whole list: on (re)connect events might have been missed.
    const resync = async () => {
      try {
        const res = await fetch(LIST_URL, { cache: "no-store" });
        if (!res.ok || cancelled) return;
        const page: { items: Product[] } = await res.json();
        if (!cancelled) setProducts(page.items);
      } catch {
        // Network error: the socket reconnects and triggers another resync.
      }
    };

    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${protocol}://${window.location.host}${WS_PATH}`);

      socket.onopen = resync;
      socket.onmessage = (event: MessageEvent<string>) => {
        const message: LiveMessage = JSON.parse(event.data);
        if (message.type === "resync") {
          resync();
        } else if (message.type === "product") {
          const { product } = message;
          setProducts((prev) => (prev.some((p) => p.id === product.id) ? prev : [product, ...prev]));
        } else if (message.type === "deleted") {
          const removed = new Set(message.ids);
          setProducts((prev) => prev.filter((p) => !removed.has(p.id)));
        }
      };
      // Instance restarted or network dropped: reconnect, nginx picks a live backend.
      socket.onclose = () => {
        if (!cancelled) reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
      };
    };

    connect();

    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);

  return (
    <>
      <header className="header">
        <h1>Каталог</h1>
        {products.length > 0 && (
          <span>
            {products.length} {productsWord(products.length)}
          </span>
        )}
      </header>

      {products.length === 0 ? (
        <div className="empty">
          <strong>Товаров пока нет</strong>
          Они появятся здесь, когда администратор добавит их через бота.
        </div>
      ) : (
        <ul className="grid">
          {products.map((product) => (
            <li key={product.id} className="card">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={product.image_url} alt={product.title} loading="lazy" />
              <h2>{product.title}</h2>
              {product.description && <p className="description">{product.description}</p>}
              <time dateTime={product.created_at} suppressHydrationWarning>
                {dateFormat.format(new Date(product.created_at))}
              </time>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
