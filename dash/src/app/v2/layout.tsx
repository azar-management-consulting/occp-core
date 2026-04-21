/**
 * v2 parallel route layout — reuses the primary providers so /(v2)
 * shares Nav + AuthGuard + CommandPalette with the legacy routes.
 *
 * Behind feature flag NEXT_PUBLIC_DASH_V2=true (checked in middleware
 * or via a redirect from the default page in a follow-up commit).
 */
export default function DashV2Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <div className="dash-v2">{children}</div>;
}
