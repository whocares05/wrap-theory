"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import CRM from "./CRM";
import HeroWrapCanvas from "./HeroWrapCanvas";
import { APIError, DeliveryZone, formatMoney, Product, publicApi, Store } from "@/lib/api";

type CartLine = {
  key: string;
  productId: string;
  name: string;
  unitPrice: number;
  modifierOptionIds: string[];
  modifiers: string[];
};

const toneFallbacks = ["orange", "green", "red"];

export default function Home() {
  const [products, setProducts] = useState<Product[]>([]);
  const [store, setStore] = useState<Store | null>(null);
  const [zones, setZones] = useState<DeliveryZone[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [cart, setCart] = useState<CartLine[]>([]);
  const [toast, setToast] = useState("");
  const [cartOpen, setCartOpen] = useState(false);
  const [checkout, setCheckout] = useState(false);
  const [crm, setCrm] = useState(false);
  const [placingOrder, setPlacingOrder] = useState(false);
  const [orderError, setOrderError] = useState("");
  const [confirmation, setConfirmation] = useState<{ orderNumber: string; publicToken: string } | null>(null);
  const [selectedOptions, setSelectedOptions] = useState<Record<string, string>>({});
  const [customer, setCustomer] = useState({ name: "", phone: "", email: "", address: "", area: "", zoneId: "", instructions: "" });
  const idempotencyKey = useRef("");

  useEffect(() => {
    publicApi.bootstrap()
      .then(({ store: storeData, menu, zones: zoneData }) => {
        setStore(storeData);
        const menuProducts = menu.categories.flatMap((category) => category.products);
        setProducts(menuProducts);
        const builder = menuProducts.find((product) => product.slug === "custom-theory");
        if (builder) {
          setSelectedOptions(Object.fromEntries(
            builder.modifierGroups.map((group) => [group.id, group.options[0]?.id ?? ""]),
          ));
        }
        setZones(zoneData);
        if (zoneData[0]) setCustomer((value) => ({ ...value, zoneId: zoneData[0].id, area: zoneData[0].areas[0] ?? "" }));
      })
      .catch((error) => setLoadError(error instanceof Error ? error.message : "The menu could not be loaded"))
      .finally(() => setLoading(false));
  }, []);

  const featured = products.filter((product) => product.isFeatured).slice(0, 3);
  const customProduct = products.find((product) => product.slug === "custom-theory");
  const selectedZone = zones.find((zone) => zone.id === customer.zoneId);
  const subtotal = cart.reduce((sum, line) => sum + line.unitPrice, 0);
  const estimatedDelivery = selectedZone && (selectedZone.freeDeliveryThreshold === null || subtotal < selectedZone.freeDeliveryThreshold)
    ? selectedZone.deliveryFee : 0;

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 2600);
  };

  const addProduct = (product: Product, optionIds: string[] = []) => {
    const options = product.modifierGroups.flatMap((group) => group.options).filter((option) => optionIds.includes(option.id));
    const unitPrice = product.price + options.reduce((sum, option) => sum + option.priceDelta, 0);
    setCart((items) => [...items, {
      key: crypto.randomUUID(), productId: product.id, name: product.name, unitPrice,
      modifierOptionIds: optionIds, modifiers: options.map((option) => option.name),
    }]);
    notify(`${product.name} added to your bag`);
  };

  const placeOrder = async (event: FormEvent) => {
    event.preventDefault();
    if (!cart.length || !selectedZone) return;
    setPlacingOrder(true);
    setOrderError("");
    idempotencyKey.current ||= crypto.randomUUID();
    try {
      const result = await publicApi.createOrder({
        customer: { name: customer.name, phone: customer.phone, email: customer.email || null, marketingConsent: false },
        items: cart.map((line) => ({ productId: line.productId, quantity: 1, modifierOptionIds: line.modifierOptionIds })),
        fulfillmentType: "delivery",
        deliveryZoneId: customer.zoneId,
        deliveryArea: customer.area,
        deliveryAddress: customer.address,
        deliveryInstructions: customer.instructions || null,
        paymentMethod: "cash_on_delivery",
      }, idempotencyKey.current);
      setConfirmation({ orderNumber: result.orderNumber, publicToken: result.publicToken });
      setCart([]);
      setCartOpen(false);
      idempotencyKey.current = "";
    } catch (error) {
      setOrderError(error instanceof APIError ? error.message : "We could not place your order. Please try again.");
    } finally {
      setPlacingOrder(false);
    }
  };

  if (crm) return <CRM onExit={() => setCrm(false)} />;
  return (
    <main>
      <nav className="nav">
        <a className="brand" href="#top" aria-label="Wrap Theory home"><span>WRAP</span><b>THEORY</b></a>
        <div className="navlinks"><a href="#menu">Menu</a><a href="#story">Our story</a><a href="#locations">Locations</a></div>
        <div className="navActions"><button className="location">⌖ Lahore</button><button className="bag" onClick={() => setCartOpen(true)} aria-label={`Shopping bag with ${cart.length} items`}>Bag <i>{cart.length}</i></button></div>
      </nav>

      <section className="hero" id="top">
        <div id="hero-3d-wrap" aria-hidden="true"><HeroWrapCanvas /></div>
        <div className="grain" />
        <div className="heroCopy">
          <div className="eyebrow"><span /> BUILT DIFFERENT. WRAPPED BETTER.</div>
          <h1>THINK<br/><em>OUTSIDE</em><br/>THE BUN.</h1>
          <p>Bold flavours. Fresh ingredients. Zero boring bites. This is street food with a theory behind it.</p>
          <div className="heroCtas"><a className="primary" href="#menu">Explore the menu <b>↗</b></a><a className="play" href="#story"><i>▶</i> Our story</a></div>
          <div className="socialProof"><div className="faces"><span>TA</span><span>SK</span><span>HM</span><span>+</span></div><p><b>4.9</b> ★★★★★<small>2,400+ happy foodies</small></p></div>
        </div>
        <div className="heroVisual" aria-label="A floating loaded wrap illustration">
          <div className="orbit orbitOne"/><div className="orbit orbitTwo"/>
          <div className="ingredient ing1">🌶️</div><div className="ingredient ing2">🥬</div><div className="ingredient ing3">🧅</div>
          <div className="wrap3d"><div className="filling">🥬 🥩 🍅</div><div className="tortilla"><span>WRAP<br/><b>THEORY</b></span></div></div>
          <div className="badge"><b>100%</b><span>FRESH<br/>DAILY</span></div><div className="scribble">worth the mess! <span>↑</span></div>
        </div>
        <div className="ticker"><div>ROLL WITH FLAVOUR ✦ WRAPPED FRESH ✦ BIG BITE ENERGY ✦ NO BORING LUNCHES ✦ ROLL WITH FLAVOUR ✦ WRAPPED FRESH ✦</div></div>
      </section>

      <section className="menu" id="menu">
        <div className="sectionHead"><div><span className="kicker">THE CULT FAVOURITES</span><h2>CHOOSE YOUR<br/><em>OBSESSION.</em></h2></div><p>Every wrap is rolled to order, loaded with personality, and best enjoyed with both hands.</p></div>
        {loading && <p className="apiNotice">Loading today&apos;s menu…</p>}
        {loadError && <p className="apiNotice error">Menu unavailable: {loadError}</p>}
        <div className="menuGrid">
          {featured.map((product, index) => <article className="menuCard" key={product.id}>
            <div className={`foodArt ${product.tone ?? toneFallbacks[index]}`}><span className="number">0{index + 1}</span><div className="miniWrap">🌯</div>{product.tag && <span className="tag">{product.tag}</span>}</div>
            <div className="cardBody"><h3>{product.name}</h3><p>{product.description}</p><div><strong>{formatMoney(product.price)}</strong><button onClick={() => addProduct(product)} aria-label={`Add ${product.name} to bag`}>+</button></div></div>
          </article>)}
        </div>
      </section>

      {customProduct && <section className="builder"><div className="builderArt"><div className="buildWrap">🌯</div><span>YOUR RULES.<br/>OUR ROLL.</span></div><div className="builderPanel"><span className="kicker">THE LAB</span><h2>BUILD YOUR<br/><em>OWN THEORY.</em></h2><p>Choose your base, load the flavour, and make lunch personal.</p>{customProduct.modifierGroups.map((group, index) => <div key={group.id}><label>0{index + 1} · PICK {group.name.toUpperCase()}</label><div className="choices">{group.options.map((option) => <button type="button" className={selectedOptions[group.id] === option.id ? "active" : ""} onClick={() => setSelectedOptions((current) => ({ ...current, [group.id]: option.id }))} key={option.id}>{option.name}</button>)}</div></div>)}<button className="primary" onClick={() => addProduct(customProduct, Object.values(selectedOptions).filter(Boolean))}>Add my creation · {formatMoney(customProduct.price + customProduct.modifierGroups.reduce((sum, group) => sum + (group.options.find((option) => option.id === selectedOptions[group.id])?.priceDelta ?? 0), 0))} ↗</button></div></section>}

      <section className="promise" id="story"><span>THE WRAP THEORY</span><h2>GOOD FOOD SHOULD<br/>MAKE A <em>POINT.</em></h2><div className="promiseGrid"><p><b>01</b><strong>Made to order</strong><small>No heat lamps. No sad lunches. Your wrap starts when you order.</small></p><p><b>02</b><strong>Big flavour energy</strong><small>Globally inspired sauces and textures in every impossible-to-put-down bite.</small></p><p><b>03</b><strong>Planet considered</strong><small>Responsible packaging, local partners, and less waste by design.</small></p></div></section>

      <section className="locations" id="locations"><div><span className="kicker">FIND YOUR FIX</span><h2>WRAPS<br/>NEAR YOU.</h2><p>{store ? `${store.address}. Serving ${store.city} hot, fresh and fast.` : "Serving Lahore hot, fresh and fast."}</p><a className="primary" href={store ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(store.address)}` : "#locations"} target="_blank" rel="noreferrer">Find the branch ↗</a></div><div className="mapCard"><span className="pin p1">W</span><span className="pin p2">W</span><span className="pin p3">W</span><div className="mapLabel"><b>Gulberg III</b><small>Single branch · Lahore</small></div></div></section>

      <footer><a className="brand" href="#top"><span>WRAP</span><b>THEORY</b></a><p>© 2026 Wrap Theory. Rolled with intention.</p><div><a href="#">Instagram</a><a href="#">TikTok</a><a href="#">Careers</a><button className="teamLink" onClick={() => setCrm(true)}>Team CRM →</button></div></footer>
      {toast && <div className="toast">✓ {toast}</div>}

      {cartOpen && <div className="overlay" onClick={() => setCartOpen(false)}><aside className="cartDrawer" onClick={(event) => event.stopPropagation()}><div className="drawerHead"><div><span className="kicker">YOUR ORDER</span><h3>THE BAG <i>{cart.length}</i></h3></div><button onClick={() => setCartOpen(false)}>×</button></div>{cart.length === 0 ? <div className="empty"><span>🌯</span><h4>YOUR BAG IS FEELING LIGHT.</h4><p>Add a theory or two. Future you will be grateful.</p><button onClick={() => setCartOpen(false)}>Explore menu</button></div> : <><div className="cartItems">{cart.map((item) => <div key={item.key}><span>🌯</span><p><b>{item.name}</b><small>{item.modifiers.join(" · ") || "Regular · Toasted"}</small></p><strong>{formatMoney(item.unitPrice)}</strong><button onClick={() => setCart((items) => items.filter((line) => line.key !== item.key))}>×</button></div>)}</div><div className="cartTotal"><p><span>Subtotal</span><b>{formatMoney(subtotal)}</b></p><small>Delivery calculated from your area</small><button className="primary" disabled={store?.ordersPaused} onClick={() => { setCheckout(true); setCartOpen(false); }}>{store?.ordersPaused ? "Ordering paused" : "Go to checkout →"}</button></div></>}</aside></div>}

      {checkout && <div className="overlay checkoutOverlay"><form className="checkout" onSubmit={placeOrder}><button type="button" className="close" onClick={() => setCheckout(false)}>×</button>{confirmation ? <div className="confirmation"><span className="kicker">ORDER CONFIRMED</span><h3>{confirmation.orderNumber}</h3><p>We&apos;ve received your order and the kitchen queue has been notified. Keep this order number for tracking.</p><button type="button" className="primary" onClick={() => { setConfirmation(null); setCheckout(false); }}>Done</button></div> : <><span className="kicker">ALMOST YOURS</span><h3>CHECKOUT</h3><div className="steps"><b>1 Details</b><span>2 Cash on delivery</span><span>3 Done</span></div><label>Full name<input required minLength={2} value={customer.name} onChange={(event) => setCustomer({ ...customer, name: event.target.value })} placeholder="Your name" /></label><label>Phone number<input required value={customer.phone} onChange={(event) => setCustomer({ ...customer, phone: event.target.value })} placeholder="+92 300 0000000" /></label><label>Email (optional)<input type="email" value={customer.email} onChange={(event) => setCustomer({ ...customer, email: event.target.value })} placeholder="you@example.com" /></label><label>Delivery zone<select required value={customer.zoneId} onChange={(event) => { const zone = zones.find((item) => item.id === event.target.value); setCustomer({ ...customer, zoneId: event.target.value, area: zone?.areas[0] ?? "" }); }}>{zones.map((zone) => <option key={zone.id} value={zone.id}>{zone.name} · {formatMoney(zone.deliveryFee)}</option>)}</select></label><label>Area<select required value={customer.area} onChange={(event) => setCustomer({ ...customer, area: event.target.value })}>{selectedZone?.areas.map((area) => <option key={area}>{area}</option>)}</select></label><label>Delivery address<textarea required minLength={8} value={customer.address} onChange={(event) => setCustomer({ ...customer, address: event.target.value })} placeholder="House, street, landmark" /></label><label>Delivery instructions (optional)<input value={customer.instructions} onChange={(event) => setCustomer({ ...customer, instructions: event.target.value })} placeholder="Gate or rider instructions" /></label><div className="payOptions"><button type="button" className="selected">● Cash on delivery</button></div><div className="checkoutSummary"><span>Subtotal: {formatMoney(subtotal)}</span><span>Estimated delivery: {formatMoney(estimatedDelivery)}</span></div>{orderError && <p className="formError" role="alert">{orderError}</p>}<button className="primary" disabled={placingOrder}>{placingOrder ? "Placing order…" : "Place order →"}</button></>}</form></div>}
    </main>
  );
}
