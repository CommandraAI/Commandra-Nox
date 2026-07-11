import { Link } from "wouter";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-background text-foreground">
      <h1 className="text-4xl font-bold mb-4 font-mono">404</h1>
      <p className="text-lg text-muted-foreground mb-8 font-mono">Page not found</p>
      <Link href="/">
        <Button variant="outline">Return to Command Center</Button>
      </Link>
    </div>
  );
}
