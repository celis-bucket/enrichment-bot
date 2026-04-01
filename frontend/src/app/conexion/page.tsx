'use client';

import { Suspense, useEffect, useState, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import { Header } from '@/components/Header';
import { getCompany, saveSpicedData } from '@/lib/api';
import type { EnrichmentV2Results } from '@/lib/types';

const FORM_STYLES = `
  :root {
    --melonn-primary: #4929A1;
    --melonn-accent: #130A5D;
    --melonn-bg: #FFFFFF;
    --melonn-text: #000000;
    --melonn-soft: #F4F2FF;
  }
  .conexion-form { font-family: 'Roboto', sans-serif; color: var(--melonn-text); }
  .conexion-form h1, .conexion-form h2, .conexion-form h3, .conexion-form h4 { font-family: 'Sora', sans-serif; }

  .bubble-section {
    background: white; border-radius: 40px; padding: 2.5rem;
    box-shadow: 0 15px 45px rgba(19, 10, 93, 0.08);
    border: 1px solid #E2E8F0; transition: 0.4s ease;
  }
  .bubble-section:hover { transform: translateY(-5px); box-shadow: 0 25px 60px rgba(73, 41, 161, 0.15); }

  .melonn-gradient { background: linear-gradient(135deg, var(--melonn-primary) 0%, var(--melonn-accent) 100%); }

  .input-elegant {
    width: 100%; padding: 14px 20px; background: #F8FAFC;
    border: 2px solid #E2E8F0; border-radius: 20px;
    outline: none; transition: 0.3s; font-size: 0.95rem;
  }
  .input-elegant:focus { border-color: var(--melonn-primary); background: white; box-shadow: 0 0 0 5px rgba(73, 41, 161, 0.12); }

  .check-pill {
    display: flex; align-items: center; gap: 10px; background: #FFFFFF;
    padding: 12px 20px; border-radius: 50px; cursor: pointer;
    border: 2px solid #F1F5F9; transition: 0.2s; font-size: 0.85rem; font-weight: 700;
    box-shadow: 0 2px 5px rgba(0,0,0,0.02);
  }
  .check-pill:hover { border-color: #CBD5E1; }
  .check-pill:has(input:checked) { background: var(--melonn-soft); border-color: var(--melonn-primary); color: var(--melonn-primary); }
  .check-pill input { display: none; }

  .dot { width: 12px; height: 12px; border-radius: 50%; }
  .slider-purple { accent-color: var(--melonn-primary); width: 100%; }

  .conexion-toast {
    position: fixed; bottom: 2rem; right: 2rem; padding: 1rem 2rem;
    border-radius: 20px; color: white; font-weight: bold; z-index: 1000;
    transform: translateY(150%); transition: 0.3s ease;
  }
  .conexion-toast.show { transform: translateY(0); }

  .season-card { border: 2px solid #F1F5F9; border-radius: 25px; padding: 25px; background: #F9FAFB; transition: 0.3s; }
  .season-card:hover { border-color: var(--melonn-primary); background: white; }
`;

const FORM_HTML = `
    <header class="melonn-gradient text-white p-8 shadow-2xl sticky top-0 z-30" style="border-radius: 0 0 20px 20px;">
        <div class="container mx-auto flex justify-between items-center">
            <div class="flex items-center gap-6">
                <img src="http://www.melonn.com/wp-content/uploads/2022/10/Logo-Melonn-Blanco-02-1.svg" alt="Melonn" class="h-12">
                <div class="h-10 w-px bg-white/30"></div>
                <div>
                    <h1 class="text-2xl font-bold tracking-tight uppercase leading-none">Motor de Calificacion Comercial</h1>
                    <p class="text-[10px] opacity-80 tracking-[0.3em] font-black uppercase mt-1">BDR Business Intelligence</p>
                </div>
            </div>
            <div class="text-[10px] font-black uppercase tracking-widest opacity-60">Calificacion Estrategica</div>
        </div>
    </header>

    <main class="container mx-auto px-6 max-w-6xl mt-16 space-y-16 pb-24">

        <!-- Seccion 1: Origen del Lead -->
        <section class="bubble-section">
            <h2 class="text-2xl font-bold text-[#130A5D] mb-8 flex items-center gap-3">1. Origen del Lead</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div><label class="block text-xs font-black text-gray-400 mb-2 uppercase italic">BDR que califica</label><input type="text" id="bdr" class="input-elegant" placeholder="Tu nombre"></div>
                <div><label class="block text-xs font-black text-gray-400 mb-2 uppercase italic">Origen de la oportunidad</label>
                    <select id="origin" class="input-elegant">
                        <option value="Inbound">Marketing Inbound (Inbound)</option>
                        <option value="Outbound">Prospeccion Propia (Outbound)</option>
                    </select>
                </div>
                <div><label class="block text-xs font-black text-gray-400 mb-2 uppercase italic">Marca del Prospecto</label><input type="text" id="brand" class="input-elegant" placeholder="Ej: Basical"></div>
                <div><label class="block text-xs font-black text-gray-400 mb-2 uppercase italic">Fecha de Conexion</label><input type="date" id="conn_date" class="input-elegant"></div>
                <div class="md:col-span-2">
                    <label class="block text-xs font-black text-gray-400 mb-2 uppercase italic">Link de HubSpot</label>
                    <input type="url" id="hubspot_link" class="input-elegant" placeholder="https://app.hubspot.com/...">
                </div>
                <div><label class="block text-xs font-black text-gray-400 mb-2 uppercase italic">Nombre del Decisor</label><input type="text" id="seller" class="input-elegant" placeholder="Nombre completo"></div>
                <div><label class="block text-xs font-black text-gray-400 mb-2 uppercase italic">Email del Contacto</label><input type="email" id="seller_email" class="input-elegant" placeholder="ejemplo@correo.com"></div>
            </div>
        </section>

        <!-- Seccion 2: Estacionalidad -->
        <section class="bubble-section">
            <h2 class="text-2xl font-bold text-[#130A5D] mb-8 flex items-center gap-3">2. Estacionalidad</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">
                <div class="season-card">
                    <div class="flex items-center gap-2 mb-4"><h4 class="text-xs font-black text-slate-500 uppercase">Temporada Normal</h4></div>
                    <label class="block text-[10px] font-bold text-slate-400 mb-1 uppercase">Ordenes / Mes</label>
                    <input type="number" id="vol_normal" class="input-elegant" placeholder="ej. 300">
                </div>
                <div class="season-card" style="border-color: #FEE2E2;">
                    <div class="flex items-center gap-2 mb-4"><h4 class="text-xs font-black text-slate-500 uppercase">Temporada Alta</h4></div>
                    <label class="block text-[10px] font-bold text-slate-400 mb-1 uppercase">Ordenes / Mes</label>
                    <input type="number" id="vol_peak" class="input-elegant" placeholder="ej. 1000">
                </div>
            </div>
            <h3 class="text-xs font-black text-slate-400 uppercase mb-4 italic">Cuales son sus temporadas altas?</h3>
            <div class="flex flex-wrap gap-3">
                <label class="check-pill"><input type="checkbox" class="season-check" value="Dia de la Madre"> DIA DE LA MADRE</label>
                <label class="check-pill"><input type="checkbox" class="season-check" value="Dia del Padre"> DIA DEL PADRE</label>
                <label class="check-pill"><input type="checkbox" class="season-check" value="Black Friday"> BLACK FRIDAY</label>
                <label class="check-pill"><input type="checkbox" class="season-check" value="Navidad"> NAVIDAD</label>
                <label class="check-pill"><input type="checkbox" class="season-check" value="San Valentin"> SAN VALENTIN</label>
                <label class="check-pill"><input type="checkbox" class="season-check" value="Cyber Monday"> CYBER MONDAY</label>
                <label class="check-pill"><input type="checkbox" class="season-check" value="Amor y Amistad"> AMOR Y AMISTAD</label>
                <label class="check-pill"><input type="checkbox" class="season-check" value="Regreso a Clases"> REGRESO A CLASES</label>
                <label class="check-pill"><input type="checkbox" class="season-check" value="Halloween"> HALLOWEEN</label>
                <label class="check-pill"><input type="checkbox" class="season-check" value="Otra"> OTRA</label>
            </div>
        </section>

        <!-- Seccion 3: Volumen de Operacion -->
        <section class="bubble-section">
            <h2 class="text-2xl font-bold text-[#130A5D] mb-8 flex items-center gap-3">3. Volumen de Operacion</h2>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mb-10">
                <div class="md:col-span-2">
                    <label class="block text-[10px] font-black text-indigo-900 mb-1.5 uppercase tracking-wider">Que producto venden?</label>
                    <input type="text" id="product_desc" class="input-elegant" placeholder="Ej: Camisetas, Maquillaje, etc.">
                </div>
                <div><label class="block text-[10px] font-black text-indigo-900 mb-1.5 uppercase tracking-wider">Ordenes D2C / Mes</label><input type="number" id="d2c_vol" class="input-elegant" placeholder="500"></div>
                <div><label class="block text-[10px] font-black text-indigo-900 mb-1.5 uppercase tracking-wider">Ordenes B2B / Mes</label><input type="number" id="b2b_vol" class="input-elegant" placeholder="50"></div>
                <div><label class="block text-[10px] font-black text-indigo-900 mb-1.5 uppercase tracking-wider">Items por Orden</label><input type="number" step="0.1" id="ito" class="input-elegant" placeholder="1.2"></div>
                <div><label class="block text-[10px] font-black text-indigo-900 mb-1.5 uppercase tracking-wider">Equipo operativo (No. Personas)</label><input type="number" id="staff_count" class="input-elegant" placeholder="0"></div>
                <div><label class="block text-[10px] font-black text-indigo-900 mb-1.5 uppercase tracking-wider">Almacenamiento en Bodega</label><input type="number" id="skus_count" class="input-elegant" placeholder="1500"></div>
                <div><label class="block text-[10px] font-black text-indigo-900 mb-1.5 uppercase tracking-wider">Peso Prom. / Orden (KG)</label><input type="number" step="0.1" id="avg_weight" class="input-elegant" placeholder="1.0"></div>
                <div><label class="block text-[10px] font-black text-indigo-900 mb-1.5 uppercase tracking-wider">Ticket Promedio</label><input type="number" id="ticket" class="input-elegant" placeholder="Ej: 160000"></div>
                <div><label class="block text-[10px] font-black text-indigo-900 mb-1.5 uppercase tracking-wider">Registro INVIMA</label>
                    <select id="invima" class="input-elegant">
                        <option value="SI cuenta">SI cuenta con INVIMA</option>
                        <option value="NO cuenta">NO cuenta con INVIMA</option>
                        <option value="No aplica">No aplica por categoria</option>
                    </select>
                </div>
                <div><label class="block text-[10px] font-black text-indigo-900 mb-1.5 uppercase tracking-wider">Tiene tiendas fisicas?</label>
                    <select id="physical_stores" class="input-elegant">
                        <option value="No">No</option>
                        <option value="Si">Si</option>
                    </select>
                </div>
                <div><label class="block text-[10px] font-black text-indigo-900 mb-1.5 uppercase tracking-wider">Pedidos por dia (Hoy)</label><input type="number" id="daily_vol" class="input-elegant" placeholder="20"></div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-12 pt-8 border-t border-slate-100">
                <div class="space-y-6">
                    <h3 class="text-xs font-black text-indigo-900 uppercase tracking-widest">Cobertura Geografica (%)</h3>
                    <div class="space-y-4">
                        <div class="space-y-1"><div class="flex justify-between text-[10px] font-bold text-indigo-900"><span>Local</span> <span id="v_local">50%</span></div><input type="range" class="slider-purple" id="p_local" min="0" max="100" value="50"></div>
                        <div class="space-y-1"><div class="flex justify-between text-[10px] font-bold text-indigo-900"><span>Nacional</span> <span id="v_nacional">50%</span></div><input type="range" class="slider-purple" id="p_nacional" min="0" max="100" value="50"></div>
                    </div>
                </div>
                <div class="space-y-6">
                    <h3 class="text-xs font-black text-indigo-900 uppercase tracking-widest">Top 3 Ciudades de Venta</h3>
                    <div class="space-y-4">
                        <div class="flex items-center gap-3"><input type="text" id="city1" class="input-elegant flex-grow" placeholder="Ciudad 1"><div class="w-24 flex items-center gap-2"><input type="range" id="p_city1" min="0" max="100" value="80" class="slider-purple"><span id="v_city1" class="text-[10px] font-black w-8">80%</span></div></div>
                        <div class="flex items-center gap-3"><input type="text" id="city2" class="input-elegant flex-grow" placeholder="Ciudad 2"><div class="w-24 flex items-center gap-2"><input type="range" id="p_city2" min="0" max="100" value="15" class="slider-purple"><span id="v_city2" class="text-[10px] font-black w-8">15%</span></div></div>
                        <div class="flex items-center gap-3"><input type="text" id="city3" class="input-elegant flex-grow" placeholder="Ciudad 3"><div class="w-24 flex items-center gap-2"><input type="range" id="p_city3" min="0" max="100" value="5" class="slider-purple"><span id="v_city3" class="text-[10px] font-black w-8">5%</span></div></div>
                    </div>
                </div>
            </div>
        </section>

        <!-- Seccion 4: Canales y Ecosistema -->
        <section class="bubble-section">
            <h2 class="text-2xl font-bold text-[#130A5D] mb-8 flex items-center gap-3">4. Canales y Ecosistema</h2>
            <h3 class="text-xs font-black text-slate-400 uppercase mb-6 italic">Por donde venden hoy?</h3>
            <div class="flex flex-wrap gap-4 mb-10">
                <label class="check-pill"><input type="checkbox" class="ch-val" value="WhatsApp"><div class="dot bg-[#25D366]"></div> WHATSAPP</label>
                <label class="check-pill"><input type="checkbox" class="ch-val" value="Instagram"><div class="dot bg-[#E4405F]"></div> INSTAGRAM</label>
                <label class="check-pill"><input type="checkbox" class="ch-val" value="Facebook"><div class="dot bg-[#1877F2]"></div> FACEBOOK</label>
                <label class="check-pill"><input type="checkbox" class="ch-val" value="Web Propia"><div class="dot bg-[#00AEEF]"></div> WEB PROPIA</label>
                <label class="check-pill"><input type="checkbox" class="ch-val" value="MercadoLibre"><div class="dot bg-[#FFE600]"></div> MERCADOLIBRE</label>
                <label class="check-pill"><input type="checkbox" class="ch-val" value="Amazon"><div class="dot bg-[#FF9900]"></div> AMAZON</label>
                <label class="check-pill"><input type="checkbox" class="ch-val" value="Rappi"><div class="dot bg-[#FF441F]"></div> RAPPI</label>
                <label class="check-pill"><input type="checkbox" class="ch-val" value="Walmart"><div class="dot bg-[#0071CE]"></div> WALMART</label>
                <label class="check-pill"><input type="checkbox" class="ch-val" value="B2B / Tiendas"><div class="dot bg-[#6366F1]"></div> B2B / TIENDAS</label>
                <label class="check-pill"><input type="checkbox" class="ch-val" value="Otro"><div class="dot bg-slate-300"></div> OTRO</label>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div><label class="block text-xs font-black text-gray-400 mb-2 uppercase italic">Canal de Mayor Venta (80/20)</label><input type="text" id="top_channel" class="input-elegant" placeholder="Ej: Shopify / Instagram"></div>
                <div><label class="block text-xs font-black text-gray-400 mb-2 uppercase italic">Plataforma CRM/Ecom</label>
                    <select id="crm_type" class="input-elegant">
                        <option>Shopify</option><option>WooCommerce</option><option>VTEX</option><option>Magento</option><option>API Propia</option><option>HubSpot (CRM)</option>
                    </select>
                </div>
                <div><label class="block text-xs font-black text-gray-400 mb-2 uppercase italic">Operacion Actual</label>
                    <select id="op_type" class="input-elegant">
                        <option value="Autogestion (Propia)">Autogestion (Propia)</option>
                        <option value="Operador 3PL Externo">Operador 3PL Externo</option>
                        <option value="Desde Casa / In House">Desde Casa / In House</option>
                        <option value="Dropshipping">Dropshipping</option>
                        <option value="Operacion Mixta">Operacion Mixta</option>
                    </select>
                </div>
                <div><label class="block text-xs font-black text-gray-400 mb-2 uppercase italic">Transportadora Actual</label><input type="text" id="courier" class="input-elegant" placeholder="Ej: Envia, Servientrega"></div>
            </div>
        </section>

        <!-- Seccion 5: Dolores Logisticos -->
        <section class="bubble-section bg-red-50/20 border-red-100">
            <h2 class="text-2xl font-bold text-red-900 mb-8 flex items-center gap-3">5. Los 10 Dolores Logisticos</h2>
            <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-8">
                <label class="check-pill"><input type="checkbox" class="pain-val" value="Retrasos"> RETRASOS</label>
                <label class="check-pill"><input type="checkbox" class="pain-val" value="Perdidas"> PERDIDAS</label>
                <label class="check-pill"><input type="checkbox" class="pain-val" value="Colapso"> COLAPSO PICO</label>
                <label class="check-pill"><input type="checkbox" class="pain-val" value="Sin Visibilidad"> SIN VISIBILIDAD</label>
                <label class="check-pill"><input type="checkbox" class="pain-val" value="Devoluciones"> DEVOLUCIONES</label>
                <label class="check-pill"><input type="checkbox" class="pain-val" value="Errores"> ERRORES</label>
                <label class="check-pill"><input type="checkbox" class="pain-val" value="Costos"> COSTOS ALTOS</label>
                <label class="check-pill"><input type="checkbox" class="pain-val" value="Tecnologia"> SIN TECH</label>
                <label class="check-pill"><input type="checkbox" class="pain-val" value="Soporte"> MAL SOPORTE</label>
                <label class="check-pill"><input type="checkbox" class="pain-val" value="No Escala"> NO ESCALA</label>
            </div>
            <textarea id="pain_notes" class="input-elegant h-24 resize-none bg-white border-red-100 mb-8" placeholder="Notas sobre dolores..."></textarea>

            <div>
                <label class="block text-[10px] font-black text-red-600 mb-1.5 uppercase tracking-wider">Tiempos de entrega promedio del cliente</label>
                <input type="text" id="delivery_times" class="input-elegant" placeholder="Ej: 24-48 horas, 3 dias, etc.">
            </div>
        </section>

        <!-- Seccion 6: Compromiso de Reunion -->
        <section class="bubble-section border-l-8 border-emerald-400">
            <div class="flex justify-between items-center mb-8">
                <h2 class="text-2xl font-bold text-emerald-900 flex items-center gap-3">6. Proxima Reunion</h2>
                <button id="btn-calendar" class="bg-white border-2 border-slate-200 px-6 py-3 rounded-full text-[10px] font-black text-slate-600 hover:border-emerald-400 transition flex items-center gap-2">
                    <img src="https://upload.wikimedia.org/wikipedia/commons/a/a5/Google_Calendar_icon_%282020%29.svg" class="w-4 h-4"> AGENDAR EN CALENDAR
                </button>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div><label class="block text-xs font-black text-gray-400 mb-2 uppercase italic">Dia de la Reunion</label><input type="date" id="meeting_date" class="input-elegant"></div>
                <div><label class="block text-xs font-black text-gray-400 mb-2 uppercase italic">Hora de la Reunion</label><input type="time" id="meeting_time" class="input-elegant"></div>
            </div>
        </section>

        <!-- CTA Principal -->
        <div class="flex flex-col items-center gap-4 py-12">
            <button id="btn-generate" class="melonn-gradient text-white px-20 py-6 rounded-full font-black text-2xl shadow-2xl hover:scale-105 active:scale-95 transition transform uppercase tracking-tighter italic">Generar Diagnostico SPICED</button>
        </div>

        <!-- Tarjeta de Resultados (Output) -->
        <div id="output-card" class="hidden opacity-0 translate-y-10 transition-all duration-700 bg-white rounded-[50px] overflow-hidden border-4 border-[#130A5D] shadow-2xl mb-24">
            <div class="melonn-gradient p-12 text-white flex justify-between items-center">
                <div>
                    <h3 class="text-3xl font-extrabold italic tracking-tighter uppercase">Diagnostico Comercial</h3>
                    <p id="res-brand-header" class="text-[10px] font-black bg-white/20 px-4 py-1.5 rounded-full inline-block uppercase mt-2"></p>
                </div>
            </div>

            <div class="p-12 bg-white space-y-12">
                <div id="structured-output" class="text-sm text-slate-700 space-y-10 font-medium leading-relaxed"></div>

                <!-- Notas Adicionales -->
                <div class="bg-indigo-50 p-8 rounded-[40px] border-2 border-indigo-100 shadow-sm">
                    <h4 class="text-lg font-black text-indigo-900 mb-4 uppercase tracking-widest italic text-center">Notas Adicionales del BDR</h4>
                    <textarea id="res_additional_notes" class="w-full bg-white border-none rounded-3xl p-6 text-sm text-slate-700 h-32 focus:ring-2 focus:ring-indigo-400 outline-none" placeholder="Anade contexto adicional para HubSpot..."></textarea>
                </div>

                <!-- Acciones de Exportacion -->
                <div class="flex gap-6 border-t border-slate-100 pt-10">
                    <button id="btn-copy-hubspot" class="flex-grow bg-[#00F5D4] text-[#130A5D] py-6 rounded-full font-black uppercase text-xs tracking-widest shadow-xl hover:bg-[#00d1b5] transition-all">Copiar para HubSpot</button>
                    <button id="btn-print" class="bg-slate-100 text-slate-600 px-10 py-6 rounded-full font-black uppercase text-xs hover:bg-slate-200 transition-all">Imprimir PDF</button>
                </div>
            </div>
        </div>

    </main>

    <div id="conexion-toast" class="conexion-toast melonn-gradient shadow-2xl">Copiado al portapapeles</div>
`;

function setVal(id: string, value: string | number | null | undefined) {
  if (value == null || value === '') return;
  const el = document.getElementById(id) as HTMLInputElement | HTMLSelectElement | null;
  if (!el) return;
  el.value = String(value);
}

function checkCheckbox(className: string, value: string) {
  const boxes = document.querySelectorAll(`.${className}`);
  boxes.forEach((cb) => {
    const input = cb as HTMLInputElement;
    if (input.value === value) {
      input.checked = true;
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });
}

function prefillFromEnrichment(data: EnrichmentV2Results) {
  // BDR = read from localStorage (set by team page)
  const bdr = localStorage.getItem('team_selected_owner');
  if (bdr) setVal('bdr', bdr);

  // Brand = company_name
  setVal('brand', data.company_name);

  // Date = today
  const today = new Date().toISOString().split('T')[0];
  setVal('conn_date', today);

  // HubSpot link
  if (data.hubspot_company_url) setVal('hubspot_link', data.hubspot_company_url);

  // vol_normal = predicted_orders_p90
  if (data.prediction?.predicted_orders_p90) setVal('vol_normal', data.prediction.predicted_orders_p90);
}

function collectFormData(): Record<string, unknown> {
  const val = (id: string) => (document.getElementById(id) as HTMLInputElement)?.value || '';
  return {
    bdr: val('bdr'),
    origin: val('origin'),
    brand: val('brand'),
    conn_date: val('conn_date'),
    hubspot_link: val('hubspot_link'),
    seller: val('seller'),
    seller_email: val('seller_email'),
    vol_normal: val('vol_normal'),
    vol_peak: val('vol_peak'),
    seasons: Array.from(document.querySelectorAll('.season-check:checked')).map((c) => (c as HTMLInputElement).value),
    product_desc: val('product_desc'),
    d2c_vol: val('d2c_vol'),
    b2b_vol: val('b2b_vol'),
    ito: val('ito'),
    staff_count: val('staff_count'),
    skus_count: val('skus_count'),
    avg_weight: val('avg_weight'),
    ticket: val('ticket'),
    invima: val('invima'),
    physical_stores: val('physical_stores'),
    daily_vol: val('daily_vol'),
    p_local: val('p_local'),
    p_nacional: val('p_nacional'),
    city1: val('city1'), p_city1: val('p_city1'),
    city2: val('city2'), p_city2: val('p_city2'),
    city3: val('city3'), p_city3: val('p_city3'),
    channels: Array.from(document.querySelectorAll('.ch-val:checked')).map((c) => (c as HTMLInputElement).value),
    top_channel: val('top_channel'),
    crm_type: val('crm_type'),
    op_type: val('op_type'),
    courier: val('courier'),
    pains: Array.from(document.querySelectorAll('.pain-val:checked')).map((p) => (p as HTMLInputElement).value),
    pain_notes: val('pain_notes'),
    delivery_times: val('delivery_times'),
    meeting_date: val('meeting_date'),
    meeting_time: val('meeting_time'),
  };
}

function restoreFromSpicedData(saved: Record<string, unknown>) {
  // Text/number/date/time inputs
  const fields = ['bdr', 'brand', 'conn_date', 'hubspot_link', 'seller', 'seller_email',
    'vol_normal', 'vol_peak', 'product_desc', 'd2c_vol', 'b2b_vol', 'ito',
    'staff_count', 'skus_count', 'avg_weight', 'ticket', 'daily_vol',
    'city1', 'city2', 'city3', 'top_channel', 'courier', 'pain_notes',
    'delivery_times', 'meeting_date', 'meeting_time'];
  fields.forEach(f => { if (saved[f]) setVal(f, saved[f] as string); });

  // Selects
  if (saved.origin) setVal('origin', saved.origin as string);
  if (saved.invima) setVal('invima', saved.invima as string);
  if (saved.physical_stores) setVal('physical_stores', saved.physical_stores as string);
  if (saved.crm_type) setVal('crm_type', saved.crm_type as string);
  if (saved.op_type) setVal('op_type', saved.op_type as string);

  // Range sliders + display labels
  ['p_local', 'p_nacional', 'p_city1', 'p_city2', 'p_city3'].forEach(id => {
    if (saved[id]) {
      setVal(id, saved[id] as string);
      const el = document.getElementById(id) as HTMLInputElement;
      if (el) el.dispatchEvent(new Event('input', { bubbles: true }));
    }
  });

  // Checkboxes
  const seasons = (saved.seasons as string[]) || [];
  seasons.forEach(s => checkCheckbox('season-check', s));
  const channels = (saved.channels as string[]) || [];
  channels.forEach(c => checkCheckbox('ch-val', c));
  const pains = (saved.pains as string[]) || [];
  pains.forEach(p => checkCheckbox('pain-val', p));
}

function attachFormHandlers(domain?: string | null) {
  // Range sliders
  const sliders = [
    { slider: 'p_local', display: 'v_local' },
    { slider: 'p_nacional', display: 'v_nacional' },
    { slider: 'p_city1', display: 'v_city1' },
    { slider: 'p_city2', display: 'v_city2' },
    { slider: 'p_city3', display: 'v_city3' },
  ];
  sliders.forEach(({ slider, display }) => {
    const el = document.getElementById(slider);
    const disp = document.getElementById(display);
    if (el && disp) {
      el.addEventListener('input', () => {
        disp.innerText = (el as HTMLInputElement).value + '%';
      });
    }
  });

  // Calendar button
  document.getElementById('btn-calendar')?.addEventListener('click', () => {
    const brand = (document.getElementById('brand') as HTMLInputElement)?.value || 'Prospecto';
    const dateInput = (document.getElementById('meeting_date') as HTMLInputElement)?.value;
    const timeInput = (document.getElementById('meeting_time') as HTMLInputElement)?.value;
    const seller = (document.getElementById('seller') as HTMLInputElement)?.value || 'Decisor';
    if (!dateInput || !timeInput) {
      showToast('Selecciona fecha y hora.');
      return;
    }
    const start = dateInput.replace(/-/g, '') + 'T' + timeInput.replace(':', '') + '00';
    const endHour = parseInt(timeInput.split(':')[0]);
    const endMin = (parseInt(timeInput.split(':')[1]) + 45).toString().padStart(2, '0');
    const end = dateInput.replace(/-/g, '') + 'T' + endHour.toString().padStart(2, '0') + endMin + '00';
    const title = encodeURIComponent(`Reunion Melonn: ${brand} / ${seller}`);
    const hsLink = (document.getElementById('hubspot_link') as HTMLInputElement)?.value || '';
    const details = encodeURIComponent(`Diagnostico Comercial SPICED.\nMarca: ${brand}\nHubSpot: ${hsLink}`);
    window.open(`https://calendar.google.com/calendar/render?action=TEMPLATE&text=${title}&dates=${start}/${end}&details=${details}`, '_blank');
  });

  // Generate SPICED + save to backend
  document.getElementById('btn-generate')?.addEventListener('click', () => {
    generateStructuredSpiced();
    if (domain) {
      const formData = collectFormData();
      saveSpicedData(domain, formData)
        .then(() => showToast('Diagnostico guardado'))
        .catch(err => console.warn('Failed to save SPICED data:', err));
    }
  });

  // Copy to HubSpot
  document.getElementById('btn-copy-hubspot')?.addEventListener('click', copyToHubSpot);

  // Print
  document.getElementById('btn-print')?.addEventListener('click', () => window.print());
}

function showToast(msg: string) {
  const t = document.getElementById('conexion-toast');
  if (!t) return;
  t.innerText = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3000);
}

function generateStructuredSpiced() {
  const val = (id: string) => (document.getElementById(id) as HTMLInputElement)?.value || '';
  const d2cVol = parseInt(val('d2c_vol')) || 0;
  const ticket = parseInt(val('ticket')) || 160000;

  const data = {
    brand: (val('brand') || 'MARCA').toUpperCase(),
    bdr: val('bdr') || 'BDR Melonn',
    seller: val('seller') || 'Decisor',
    email: val('seller_email') || 'Email N/A',
    conn_date: val('conn_date') || 'No especificada',
    vol: d2cVol,
    peak: val('vol_peak') || '0',
    daily: val('daily_vol') || '0',
    ito: val('ito') || '1.2',
    staff: val('staff_count') || '0',
    ticket: ticket,
    skus: val('skus_count') || '0',
    invima: val('invima'),
    weight: val('avg_weight') || '1',
    product: val('product_desc') || 'N/A',
    stores: val('physical_stores'),
    channels: Array.from(document.querySelectorAll('.ch-val:checked')).map((c) => (c as HTMLInputElement).value).join(', '),
    top_ch: val('top_channel') || 'No especificado',
    crm: val('crm_type'),
    pains: Array.from(document.querySelectorAll('.pain-val:checked')).map((p) => (p as HTMLInputElement).value).join(', '),
    notes: val('pain_notes') || 'Sin notas adicionales.',
    op: val('op_type'),
    courier: val('courier') || 'N/A',
    city1: val('city1') || 'C1',
    v_city1: document.getElementById('v_city1')?.innerText || '80%',
    city2: val('city2') || 'C2',
    v_city2: document.getElementById('v_city2')?.innerText || '15%',
    city3: val('city3') || 'C3',
    v_city3: document.getElementById('v_city3')?.innerText || '5%',
    sla: val('delivery_times') || 'No especificado',
    hs_link: val('hubspot_link') || 'N/A',
    meet_date: val('meeting_date'),
    meet_time: val('meeting_time'),
    localPct: document.getElementById('v_local')?.innerText || '50%',
    nacPct: document.getElementById('v_nacional')?.innerText || '50%',
  };

  const salesTotal = data.vol * data.ticket;

  const html = `
    <div class="space-y-12">
      <div>
        <h4 class="text-xl font-black text-indigo-900 mb-6 flex items-center gap-3">1. Resumen segun metodologia SPICED</h4>
        <div class="space-y-6 pl-6 border-l-8 border-indigo-200">
          <p><strong>Situacion:</strong> <u>${data.brand}</u> es una marca de <u>${data.product}</u> conectada el dia <u>${data.conn_date}</u> que opera bajo un esquema de <u>${data.op}</u> e integra su ecosistema con <u>${data.crm}</u>. Registran un promedio regular de <u>${data.vol} pedidos mensuales</u> (${data.daily} diarios) con picos de <u>${data.peak} ordenes</u>. Su cobertura principal es con una distribucion de <u>${data.localPct} Local</u> y <u>${data.nacPct} Nacional</u>.</p>
          <p><strong>Pain:</strong> Se identifican dolores criticos en <u>${data.pains}</u>. Detalle compartido: ${data.notes}. Actualmente operan con la transportadora <u>${data.courier}</u>.</p>
          <p><strong>Impacto:</strong> La optimizacion elevaria el cumplimiento de los tiempos de entrega (actualmente en <u>${data.sla}</u>) y liberaria la carga operativa del equipo de <u>${data.staff} personas</u>, permitiendo escalar la marca sin errores de inventario ni demoras.</p>
          <p><strong>Evento Critico:</strong> Es critico implementar cambios antes de los proximos picos comerciales registrados para asegurar la capacidad de respuesta operativa.</p>
          <p><strong>Decision:</strong> <u>${data.seller}</u> esta evaluando la viabilidad de tercerizar con Melonn. <strong>Registro INVIMA: ${data.invima}</strong>. <strong>Tiendas Fisicas: ${data.stores}</strong>. Interes en simulaciones de costo para su Almacenamiento en Bodega de ${data.skus} unidades.</p>
        </div>
      </div>

      <div>
        <h4 class="text-xl font-black text-indigo-900 mb-6 flex items-center gap-3">2. Insights clave del negocio</h4>
        <ul class="space-y-4 pl-8 list-disc text-slate-700">
          <li><strong>Volumen & Ventas:</strong> ${data.vol} ordenes/mes con un ticket promedio de $${ticket.toLocaleString()}. Esto representa ventas estimadas de ~$${(salesTotal / 1000000).toFixed(1)}M mensuales.</li>
          <li><strong>Operacion:</strong> Almacenamiento en Bodega de ${data.skus} unidades con un peso promedio por orden de ${data.weight}kg.</li>
          <li><strong>Equipo:</strong> Estructura operativa de ${data.staff} personas.</li>
          <li><strong>Geografia:</strong> Concentracion en ${data.city1} (${data.v_city1}), ${data.city2} (${data.v_city2}), ${data.city3} (${data.v_city3}).</li>
          <li><strong>Canales:</strong> ${data.channels}.</li>
          <li><strong>HubSpot:</strong> <a href="${data.hs_link}" target="_blank" class="text-indigo-600 underline font-bold">${data.hs_link}</a></li>
        </ul>
      </div>

      <div>
        <h4 class="text-xl font-black text-indigo-900 mb-6 flex items-center gap-3">3. Compromisos Melonn</h4>
        <div class="bg-indigo-50 p-8 rounded-[40px] border border-indigo-100">
          <ul class="text-xs space-y-3 font-bold text-indigo-900 uppercase italic tracking-wider">
            <li>Realizar simulacion detallada de costos operativos proyectados vs operacion actual.</li>
            <li>Preparar auditoria tecnica de integracion con ${data.crm}.</li>
            <li>Enviar propuesta comercial formal con el BDR ${data.bdr} a cargo.</li>
          </ul>
        </div>
      </div>

      ${data.meet_date ? `
      <div class="bg-emerald-50 p-8 rounded-[40px] border-2 border-emerald-100">
        <h4 class="text-xl font-black text-emerald-900 mb-4 flex items-center gap-2">Proxima Cita Agendada</h4>
        <p class="text-sm">Reunion de seguimiento confirmada para el dia <strong>${data.meet_date}</strong> a las <strong>${data.meet_time}</strong>.</p>
      </div>` : ''}
    </div>
  `;

  const outputEl = document.getElementById('structured-output');
  const brandHeader = document.getElementById('res-brand-header');
  const card = document.getElementById('output-card');
  if (outputEl) outputEl.innerHTML = html;
  if (brandHeader) brandHeader.innerText = data.brand;
  if (card) {
    card.classList.remove('hidden');
    setTimeout(() => {
      card.classList.remove('opacity-0', 'translate-y-10');
      card.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  }
}

function copyToHubSpot() {
  const content = document.getElementById('structured-output')?.innerText || '';
  const extra = (document.getElementById('res_additional_notes') as HTMLTextAreaElement)?.value || '';
  const brand = (document.getElementById('brand') as HTMLInputElement)?.value || '';
  let finalString = `--- DIAGNOSTICO ESTRATEGICO MELONN: ${brand.toUpperCase()} ---\n\n${content}`;
  if (extra.trim() !== '') finalString += `\n\nNOTAS ADICIONALES BDR:\n${extra}`;

  navigator.clipboard.writeText(finalString).then(() => {
    showToast('Copiado al portapapeles');
  }).catch(() => {
    // Fallback
    const el = document.createElement('textarea');
    el.value = finalString;
    document.body.appendChild(el);
    el.select();
    document.execCommand('copy');
    document.body.removeChild(el);
    showToast('Copiado al portapapeles');
  });
}

function ConexionPageInner() {
  const searchParams = useSearchParams();
  const domain = searchParams.get('domain');
  const formRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(!!domain);
  const [companyName, setCompanyName] = useState<string | null>(null);
  const [enrichmentData, setEnrichmentData] = useState<EnrichmentV2Results | null>(null);

  // Effect 1: fetch enrichment data
  useEffect(() => {
    if (!domain) {
      setLoading(false);
      return;
    }
    getCompany(domain)
      .then((result) => {
        setEnrichmentData(result);
        setCompanyName(result.company_name || domain || null);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [domain]);

  // Effect 2: runs AFTER DOM paint when loading is done — attach handlers + prefill
  useEffect(() => {
    if (loading) return;
    attachFormHandlers(domain);
    if (enrichmentData) {
      // Saved SPICED data takes priority over enrichment defaults
      if (enrichmentData.spiced_data && typeof enrichmentData.spiced_data === 'object' && Object.keys(enrichmentData.spiced_data).length > 0) {
        restoreFromSpicedData(enrichmentData.spiced_data as Record<string, unknown>);
      } else {
        prefillFromEnrichment(enrichmentData);
      }
    }
  }, [loading, enrichmentData, domain]);

  return (
    <div className="min-h-screen bg-[#F8FAFC]">
      <Header />
      <link href="https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&family=Roboto:wght@400;500;700&display=swap" rel="stylesheet" />
      <style dangerouslySetInnerHTML={{ __html: FORM_STYLES }} />

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-melonn-purple mb-4" />
          <p className="text-sm text-gray-500">Cargando datos de {domain}...</p>
        </div>
      ) : (
        <>
          {companyName && (
            <div className="max-w-6xl mx-auto px-6 mt-6">
              <div className="bg-melonn-purple/5 border border-melonn-purple/20 rounded-2xl px-6 py-4 flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-melonn-green" />
                <span className="text-sm text-melonn-navy">
                  Datos pre-cargados de <strong>{companyName}</strong> ({domain}). Revisa y completa los campos faltantes.
                </span>
              </div>
            </div>
          )}
          <div ref={formRef} className="conexion-form" dangerouslySetInnerHTML={{ __html: FORM_HTML }} />
        </>
      )}
    </div>
  );
}

export default function ConexionPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#F8FAFC]">
        <Header />
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-melonn-purple" />
        </div>
      </div>
    }>
      <ConexionPageInner />
    </Suspense>
  );
}
