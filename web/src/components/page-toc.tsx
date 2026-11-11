export function PageToc({ items }: { items: Array<{ href: string; label: string }> }) {
  return (
    <nav aria-label="On this page" className="sticky top-0 z-20 -mx-4 border-b border-teal/10 bg-cream/95 px-4 py-3 backdrop-blur">
      <p className="text-sm font-semibold uppercase tracking-[0.12em] text-teal/70">On this page</p>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-2 text-base font-semibold">
        {items.map((item) => (
          <li key={item.href}>
            <a className="text-teal underline decoration-teal/30 underline-offset-2" href={item.href}>
              {item.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
