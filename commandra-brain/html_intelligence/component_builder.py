"""Component Builder -- generates the skeleton for a common, reusable UI
component (button, card, modal, nav, form field, table) matching the
requested stack, ready for the Coding/Frontend Agent to flesh out."""

from __future__ import annotations

_TAILWIND_REACT_TEMPLATES = {
    "button": (
        "export function Button({ children, variant = 'primary', ...props }: ButtonProps) {\n"
        "  const base = 'inline-flex items-center justify-center rounded-md text-sm font-medium px-4 py-2 "
        "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-50';\n"
        "  const variants = {\n"
        "    primary: 'bg-primary text-white hover:bg-primary/90 focus-visible:ring-primary',\n"
        "    secondary: 'bg-neutral-100 text-neutral-900 hover:bg-neutral-200',\n"
        "    ghost: 'hover:bg-neutral-100 text-neutral-900',\n"
        "  };\n"
        "  return (\n"
        "    <button className={`${base} ${variants[variant]}`} {...props}>\n"
        "      {children}\n"
        "    </button>\n"
        "  );\n"
        "}\n"
    ),
    "card": (
        "export function Card({ title, children }: CardProps) {\n"
        "  return (\n"
        "    <div className=\"rounded-lg border border-neutral-200 bg-white p-6 shadow-sm\">\n"
        "      {title && <h3 className=\"mb-2 text-h3 font-semibold text-neutral-900\">{title}</h3>}\n"
        "      <div className=\"text-body text-neutral-700\">{children}</div>\n"
        "    </div>\n"
        "  );\n"
        "}\n"
    ),
    "modal": (
        "export function Modal({ open, onClose, children }: ModalProps) {\n"
        "  if (!open) return null;\n"
        "  return (\n"
        "    <div role=\"dialog\" aria-modal=\"true\" className=\"fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4\">\n"
        "      <div className=\"w-full max-w-md rounded-lg bg-white p-6 shadow-xl\">\n"
        "        <button aria-label=\"Close\" onClick={onClose} className=\"absolute right-4 top-4 text-neutral-500 hover:text-neutral-900\">×</button>\n"
        "        {children}\n"
        "      </div>\n"
        "    </div>\n"
        "  );\n"
        "}\n"
    ),
    "nav": (
        "export function Nav({ links }: NavProps) {\n"
        "  return (\n"
        "    <nav className=\"flex items-center justify-between px-6 py-4\">\n"
        "      <span className=\"text-h3 font-semibold\">Logo</span>\n"
        "      <ul className=\"hidden gap-6 md:flex\">\n"
        "        {links.map((link) => (\n"
        "          <li key={link.href}><a href={link.href} className=\"text-body text-neutral-700 hover:text-primary\">{link.label}</a></li>\n"
        "        ))}\n"
        "      </ul>\n"
        "    </nav>\n"
        "  );\n"
        "}\n"
    ),
    "form_field": (
        "export function FormField({ label, id, error, ...props }: FormFieldProps) {\n"
        "  return (\n"
        "    <div className=\"flex flex-col gap-1\">\n"
        "      <label htmlFor={id} className=\"text-small font-medium text-neutral-700\">{label}</label>\n"
        "      <input id={id} className=\"rounded-md border border-neutral-300 px-3 py-2 text-body focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary\" {...props} />\n"
        "      {error && <span className=\"text-small text-danger\">{error}</span>}\n"
        "    </div>\n"
        "  );\n"
        "}\n"
    ),
    "table": (
        "export function DataTable({ columns, rows }: DataTableProps) {\n"
        "  return (\n"
        "    <div className=\"overflow-x-auto rounded-lg border border-neutral-200\">\n"
        "      <table className=\"w-full text-left text-small\">\n"
        "        <thead className=\"bg-neutral-50 text-neutral-500\">\n"
        "          <tr>{columns.map((c) => <th key={c.key} className=\"px-4 py-3 font-medium\">{c.label}</th>)}</tr>\n"
        "        </thead>\n"
        "        <tbody className=\"divide-y divide-neutral-100\">\n"
        "          {rows.map((row, i) => (\n"
        "            <tr key={i} className=\"hover:bg-neutral-50\">{columns.map((c) => <td key={c.key} className=\"px-4 py-3\">{row[c.key]}</td>)}</tr>\n"
        "          ))}\n"
        "        </tbody>\n"
        "      </table>\n"
        "    </div>\n"
        "  );\n"
        "}\n"
    ),
}


def build_component(component_kind: str, stack: str = "react_tailwind") -> str:
    """Returns a skeleton for `component_kind` (button/card/modal/nav/
    form_field/table). Only the react+tailwind stack has hand-authored
    templates today; other stacks get a structured TODO scaffold that still
    names the exact accessibility/interaction requirements to satisfy."""
    if stack == "react_tailwind" and component_kind in _TAILWIND_REACT_TEMPLATES:
        return _TAILWIND_REACT_TEMPLATES[component_kind]
    return (
        f"// TODO: implement a production-quality '{component_kind}' component for stack '{stack}'.\n"
        f"// Must include: semantic markup, visible focus states, keyboard support, and responsive behavior.\n"
    )


def available_components() -> list[str]:
    return sorted(_TAILWIND_REACT_TEMPLATES.keys())
