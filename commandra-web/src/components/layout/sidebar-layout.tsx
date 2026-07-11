import { forwardRef } from "react";
import { cn } from "@/lib/utils";

const SidebarLayout = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, children, ...props }, ref) => {
  return (
    <div ref={ref} className={cn("flex h-screen w-full overflow-hidden bg-background", className)} {...props}>
      {children}
    </div>
  );
});
SidebarLayout.displayName = "SidebarLayout";

const Sidebar = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, children, ...props }, ref) => {
  return (
    <div ref={ref} className={cn("flex w-[220px] flex-col border-r border-sidebar-border bg-sidebar shrink-0 transition-all duration-300", className)} {...props}>
      {children}
    </div>
  );
});
Sidebar.displayName = "Sidebar";

const MainContent = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, children, ...props }, ref) => {
  return (
    <div ref={ref} className={cn("flex flex-1 flex-col overflow-hidden relative", className)} {...props}>
      {children}
    </div>
  );
});
MainContent.displayName = "MainContent";

export { SidebarLayout, Sidebar, MainContent };
