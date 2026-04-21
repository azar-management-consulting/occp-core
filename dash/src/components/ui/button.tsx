import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent,#6366f1)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-elev,#18181b)] disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--accent,#6366f1)] text-white shadow hover:opacity-90",
        destructive:
          "bg-[var(--danger,#dc2626)] text-white shadow hover:opacity-90",
        outline:
          "border border-[var(--border-subtle,#333)] bg-transparent text-[var(--fg,#fafafa)] hover:bg-[var(--bg-elev,#18181b)]",
        secondary:
          "bg-[var(--bg-elev,#18181b)] text-[var(--fg,#fafafa)] shadow-sm hover:opacity-90",
        ghost: "hover:bg-[var(--bg-elev,#18181b)] text-[var(--fg,#fafafa)]",
        link: "text-[var(--accent,#6366f1)] underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-md px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
