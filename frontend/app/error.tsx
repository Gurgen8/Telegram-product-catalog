"use client";

export default function CatalogError({ reset }: { error: Error; reset: () => void }) {
  return (
    <main>
      <header className="header">
        <h1>Каталог</h1>
      </header>
      <div className="empty">
        <strong>Не удалось загрузить товары</strong>
        Проверьте соединение и попробуйте ещё раз.
        <br />
        <button type="button" onClick={reset}>
          Повторить
        </button>
      </div>
    </main>
  );
}
