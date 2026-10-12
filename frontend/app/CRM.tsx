"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { formatMoney, staffApi } from "@/lib/api";
import { getSupabaseBrowserClient } from "@/lib/supabase";

type Row = Record<string, unknown>;
type Staff = { userId: string; email: string; displayName: string; role: "admin" | "manager" };
type Dashboard = {
  today: { revenue: number; orders: number; averageOrderValue: number; averagePrepMinutes: number | null };
  recentOrders: Row[];
  topProducts: Row[];
  lowStock: Row[];
};

const nextStatus: Record<string, string | undefined> = {
  pending: "confirmed", confirmed: "preparing", preparing: "ready", ready: "out_for_delivery", out_for_delivery: "delivered",
};

function Login({ onAuthenticated, onExit }: { onAuthenticated: (session: Session) => void; onExit: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const supabase = getSupabaseBrowserClient();
      const result = await supabase.auth.signInWithPassword({ email, password });
      if (result.error) throw result.error;
      if (result.data.session) onAuthenticated(result.data.session);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  };

  return <main className="crmLogin"><form onSubmit={submit}><button type="button" className="crmBrand" onClick={onExit}><span>WRAP</span> THEORY <small>OPS</small></button><span className="kicker">STAFF ACCESS</span><h1>Welcome back.</h1><p>Sign in with your invited staff account. Customer accounts are not enabled.</p><label>Email<input type="email" required autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label><label>Password<input type="password" required autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>{error && <p className="formError" role="alert">{error}</p>}<button className="primary" disabled={busy}>{busy ? "Signing in…" : "Sign in →"}</button><button type="button" className="backStore" onClick={onExit}>← Back to storefront</button></form></main>;
}

export default function CRM({ onExit }: { onExit: () => void }) {
  const [session, setSession] = useState<Session | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);
  const [staff, setStaff] = useState<Staff | null>(null);
  const [tab, setTab] = useState("Overview");
  const [search, setSearch] = useState("");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    try {
      const supabase = getSupabaseBrowserClient();
      supabase.auth.getSession().then(({ data }) => { setSession(data.session); setCheckingSession(false); });
      const { data } = supabase.auth.onAuthStateChange((_event, current) => setSession(current));
      return () => data.subscription.unsubscribe();
    } catch (caught) {
      queueMicrotask(() => {
        setError(caught instanceof Error ? caught.message : "Authentication is unavailable");
        setCheckingSession(false);
      });
    }
  }, []);

  const token = session?.access_token;
  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError("");
    try {
      const currentStaff = staff ?? await staffApi.me(token);
      setStaff(currentStaff);
      if (tab === "Overview") {
        setDashboard(await staffApi.dashboard(token) as unknown as Dashboard);
        setRows([]);
      } else if (tab === "Orders") {
        setRows((await staffApi.orders(token, search)).data);
      } else if (tab === "Customers") {
        setRows((await staffApi.customers(token)).data);
      } else if (tab === "Menu & stock") {
        const [products, inventory] = await Promise.all([staffApi.products(token), staffApi.inventory(token)]);
        setRows([...products.map((row) => ({ ...row, rowType: "product" })), ...inventory.map((row) => ({ ...row, rowType: "stock" }))]);
      } else if (tab === "Campaigns") {
        setRows(await staffApi.campaigns(token));
      } else if (tab === "Team tasks") {
        setRows(await staffApi.tasks(token));
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The dashboard could not be loaded");
    } finally {
      setLoading(false);
    }
  }, [token, tab, search, staff]);

  useEffect(() => {
    const initial = window.setTimeout(() => void load(), 0);
    const refresh = window.setInterval(() => {
      if (tab === "Overview" || tab === "Orders") void load();
    }, 15_000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(refresh);
    };
  }, [load, tab]);

  const displayRows = useMemo(() => {
    const orderRows = tab === "Overview" ? dashboard?.recentOrders ?? [] : rows;
    return orderRows.filter((row) => JSON.stringify(row).toLowerCase().includes(search.toLowerCase()));
  }, [tab, dashboard?.recentOrders, rows, search]);

  const advanceOrder = async (row: Row) => {
    if (!token || typeof row.id !== "string" || typeof row.status !== "string") return;
    const status = nextStatus[row.status];
    if (!status) return;
    try {
      await staffApi.updateOrderStatus(token, row.id, status);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Order update failed");
    }
  };

  const signOut = async () => {
    await getSupabaseBrowserClient().auth.signOut();
    setSession(null);
    setStaff(null);
  };

  if (checkingSession) return <main className="crmLogin"><p>Checking staff session…</p></main>;
  if (!session) return <Login onAuthenticated={setSession} onExit={onExit} />;

  const date = new Intl.DateTimeFormat("en-PK", { weekday: "long", day: "2-digit", month: "short" }).format(new Date()).toUpperCase();
  return <main className="crm">
    <aside className="crmSide"><button className="crmBrand" onClick={onExit}><span>WRAP</span> THEORY <small>OPS</small></button><nav>{["Overview", "Orders", "Customers", "Menu & stock", "Campaigns", "Team tasks"].map((name, index) => <button key={name} className={tab === name ? "active" : ""} onClick={() => setTab(name)}><i>{["⌁", "▤", "♙", "◫", "✦", "✓"][index]}</i>{name}{name === "Orders" && dashboard?.today.orders ? <b>{dashboard.today.orders}</b> : null}</button>)}</nav><div className="storeStatus"><span>STORE STATUS</span><p><i/> Backend connected</p><small>Live Supabase operations</small></div><button className="userChip" onClick={signOut}><span>{staff?.displayName.split(" ").map((part) => part[0]).slice(0, 2).join("") ?? "WT"}</span><p><b>{staff?.displayName ?? "Staff"}</b><small>{staff?.role ?? "Authorizing…"}</small></p><i>Sign out</i></button></aside>
    <section className="crmMain"><header><div><span className="kicker">{date}</span><h1>{tab}</h1></div><div className="crmActions"><button onClick={() => void load()} aria-label="Refresh">↻</button><button aria-label="Notifications">♢</button></div></header>
      {error && <p className="dashboardError" role="alert">{error}</p>}
      {loading && <p className="dashboardLoading">Refreshing live data…</p>}
      {tab === "Overview" && dashboard && <><div className="metrics"><article><span>TODAY&apos;S REVENUE</span><b>{formatMoney(dashboard.today.revenue)}</b><small>Confirmed and fulfilled orders</small></article><article><span>ORDERS</span><b>{dashboard.today.orders}</b><small>Today&apos;s accepted orders</small></article><article><span>AVG. ORDER VALUE</span><b>{formatMoney(dashboard.today.averageOrderValue)}</b><small>Server-calculated total</small></article><article className={dashboard.lowStock.length ? "alertMetric" : ""}><span>LOW STOCK ITEMS</span><b>{dashboard.lowStock.length}</b><small>{dashboard.lowStock.length ? "Restock attention needed" : "Stock levels healthy"}</small></article></div><div className="crmGrid"><article className="salesChart"><div className="widgetHead"><div><span>LIVE OPERATIONS</span><h3>Today&apos;s order volume</h3></div></div><div className="chart"><div className="bars">{[20, 35, 28, 48, 42, 64, 58, 74, 68, Math.min(95, 20 + dashboard.today.orders), 55, 35].map((height, index) => <div key={index}><i style={{ height: `${height}%` }} className={index === 9 ? "hot" : ""}/><span>{index + 11 > 12 ? index - 1 : index + 11}{index + 11 >= 12 ? "p" : "a"}</span></div>)}</div></div></article><article className="topWraps"><div className="widgetHead"><div><span>MENU SIGNAL</span><h3>Top wraps today</h3></div></div>{dashboard.topProducts.length ? dashboard.topProducts.map((product, index) => <div className="rank" key={String(product.name)}><b>0{index + 1}</b><span className={`thumb t${index}`}>🌯</span><p><strong>{String(product.name)}</strong><small>{String(product.quantity)} sold</small></p><em>{formatMoney(Number(product.revenue))}</em></div>) : <p className="emptyWidget">No fulfilled orders yet today.</p>}</article></div></>}
      {(tab === "Overview" || tab === "Orders") && <article className="ordersTable"><div className="widgetHead"><div><span>LIVE QUEUE</span><h3>{tab === "Overview" ? "Recent orders" : "All orders"}</h3></div><div className="tableTools"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search orders..."/></div></div><div className="table"><div className="tr th"><span>ORDER</span><span>CUSTOMER</span><span>TOTAL</span><span>PAYMENT</span><span>STATUS</span><span>ACTION</span></div>{displayRows.map((row) => <div className="tr" key={String(row.id)}><b>{String(row.orderNumber)}</b><span>{String(row.customerName)}</span><b>{formatMoney(Number(row.total))}</b><span>{String(row.paymentStatus ?? "pending").replaceAll("_", " ")}</span><i className={`status ${String(row.status).replaceAll("_", "")}`}>{String(row.status).replaceAll("_", " ")}</i><button disabled={!nextStatus[String(row.status)]} onClick={() => void advanceOrder(row)}>{nextStatus[String(row.status)]?.replaceAll("_", " ") ?? "Done"}</button></div>)}</div></article>}
      {!["Overview", "Orders"].includes(tab) && <article className="ordersTable"><div className="widgetHead"><div><span>OPERATIONS</span><h3>{tab}</h3></div></div><div className="opsCards">{rows.length ? rows.map((row, index) => <div className="opsCard" key={String(row.id ?? index)}>{Object.entries(row).filter(([key]) => !["id", "createdAt", "updatedAt", "rowType"].includes(key)).slice(0, 6).map(([key, value]) => <p key={key}><span>{key.replaceAll(/([A-Z])/g, " $1")}</span><b>{typeof value === "number" && /value|price|total/i.test(key) ? formatMoney(value) : String(value ?? "—")}</b></p>)}</div>) : <div className="emptyWidget">No records yet.</div>}</div></article>}
    </section>
  </main>;
}
