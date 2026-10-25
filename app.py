import sqlite3
import os
from abc import ABC, abstractmethod
from flask import Flask, request, jsonify, render_template_string

# ==============================================================================
# 1. EXCEPCIONES PERSONALIZADAS DEL DOMINIO (Consigna 2)
# ==============================================================================
class EntradaInvalidaError(Exception):
    """Regla de negocio: Sin cupo o regla rota."""
    pass

class DatoInvalidoError(Exception):
    """Regla de validación: Precios inválidos o datos vacíos."""
    pass


# ==============================================================================
# 2. INTERFAZ PURA Reportable (Consigna 2)
# ==============================================================================
class Reportable(ABC):
    @abstractmethod
    def generar_resumen(self) -> dict:
        """Contrato formal sin estado propio."""
        pass


# ==============================================================================
# 3. CLASES Y POLIMORFISMO (Consigna 2)
# ==============================================================================
class Cliente:
    def __init__(self, id_cliente: int, nombre: str, dni: str, email: str):
        if not nombre or not nombre.strip():
            raise DatoInvalidoError("Falta ingresar el Nombre del cliente.")
        if not dni or not str(dni).strip():
            raise DatoInvalidoError("Falta ingresar el DNI del cliente.")
        if not email or not email.strip():
            raise DatoInvalidoError("Falta ingresar el Email del cliente.")
            
        self.id_cliente = id_cliente
        self.nombre = nombre.strip()
        self.dni = str(dni).strip()
        self.email = email.strip()


class EventoBase(Reportable, ABC):
    """Clase base abstracta. No permite instanciación directa."""
    def __init__(self, id_evento: int, nombre: str, sala: str, cupo_maximo: int, tipo: str):
        if not nombre or not nombre.strip():
            raise DatoInvalidoError("Falta ingresar el Nombre del evento.")
        if not sala or not sala.strip():
            raise DatoInvalidoError("Falta ingresar la Sala del evento.")
        if cupo_maximo <= 0:
            raise DatoInvalidoError("El Cupo Máximo debe ser un número entero mayor a 0.")

        self.id_evento = id_evento
        self.nombre = nombre.strip()
        self.sala = sala.strip()
        self.cupo_maximo = cupo_maximo
        self.tipo = tipo
        self.entradas_vendidas = []

    @abstractmethod
    def calcular_precio_final(self, precio_base: float) -> float:
        """Método abstracto polimórfico."""
        pass

    def tiene_cupo_disponible(self) -> bool:
        return len(self.entradas_vendidas) < self.cupo_maximo

    def vender_entrada(self, cliente: Cliente, precio_base: float, nro_ticket: int):
        if precio_base <= 0:
            raise DatoInvalidoError("El Precio Base debe ser mayor a $0.00.")

        if not self.tiene_cupo_disponible():
            raise EntradaInvalidaError(f"No hay cupo disponible para '{self.nombre}' (Capacidad de {self.cupo_maximo} lugares agotada).")

        precio_final = self.calcular_precio_final(precio_base)
        nueva_entrada = Entrada(nro_ticket, self, cliente, precio_final)
        self.entradas_vendidas.append(nueva_entrada)
        return nueva_entrada

    def generar_resumen(self) -> dict:
        return {
            "evento": self.nombre,
            "tipo": self.tipo,
            "sala": self.sala,
            "vendidas": len(self.entradas_vendidas),
            "cupo": self.cupo_maximo,
            "recaudado": sum(e.precio for e in self.entradas_vendidas)
        }


class EventoEstandar(EventoBase):
    def __init__(self, id_evento: int, nombre: str, sala: str, cupo_maximo: int):
        super().__init__(id_evento, nombre, sala, cupo_maximo, "Estándar")

    def calcular_precio_final(self, precio_base: float) -> float:
        return precio_base


class EventoVIP(EventoBase):
    def __init__(self, id_evento: int, nombre: str, sala: str, cupo_maximo: int):
        super().__init__(id_evento, nombre, sala, cupo_maximo, "VIP")

    def calcular_precio_final(self, precio_base: float) -> float:
        return precio_base * 1.25


class Entrada(Reportable):
    def __init__(self, numero: int, evento: EventoBase, cliente: Cliente, precio: float):
        self.numero = numero
        self.evento = evento
        self.cliente = cliente
        self.precio = precio

    def generar_resumen(self) -> dict:
        return {
            "ticket_nro": self.numero,
            "evento": self.evento.nombre,
            "cliente": f"{self.cliente.nombre} (DNI: {self.cliente.dni})",
            "precio": self.precio
        }


# ==============================================================================
# 4. BASE DE DATOS SQLITE INICIALIZADA EN LIMPIO (CON DNI)
# ==============================================================================
def init_db():
    conn = sqlite3.connect("ticketera.db")
    cur = conn.cursor()
    
    # Si la tabla clientes existía sin la columna DNI, la actualizamos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            dni TEXT NOT NULL,
            email TEXT NOT NULL
        )
    """)
    
    # Comprobación de migración para bases de datos ya creadas
    cur.execute("PRAGMA table_info(clientes)")
    columnas = [col[1] for col in cur.fetchall()]
    if "dni" not in columnas:
        cur.execute("DROP TABLE IF EXISTS entradas")
        cur.execute("DROP TABLE IF EXISTS clientes")
        cur.execute("""
            CREATE TABLE clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                dni TEXT NOT NULL,
                email TEXT NOT NULL
            )
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            sala TEXT NOT NULL,
            cupo_maximo INTEGER NOT NULL,
            tipo TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS entradas (
            numero INTEGER PRIMARY KEY AUTOINCREMENT,
            evento_id INTEGER,
            cliente_id INTEGER,
            precio REAL,
            FOREIGN KEY(evento_id) REFERENCES eventos(id),
            FOREIGN KEY(cliente_id) REFERENCES clientes(id)
        )
    """)
    conn.commit()
    conn.close()

init_db()


# ==============================================================================
# 5. APLICACIÓN WEB FLASK
# ==============================================================================
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ticketera Cultural - Sistema Administrativo</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 font-sans min-h-screen p-4 md:p-8">

  <!-- MODAL DE ALERTA SIMPLE -->
  <div id="modal-alerta" class="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 hidden">
    <div class="bg-slate-900 border border-slate-700 max-w-md w-full rounded-2xl p-6 shadow-2xl space-y-4">
      <div class="flex items-center gap-3">
        <div id="modal-icono-box" class="p-3 rounded-xl bg-amber-500/20 text-amber-400 font-bold text-xl">⚠️</div>
        <div>
          <h3 id="modal-titulo" class="text-base font-bold text-white">Dato faltante o inválido</h3>
          <p class="text-xs text-slate-400">Notificación del sistema</p>
        </div>
      </div>
      <div id="modal-mensaje" class="text-sm bg-slate-950 p-4 rounded-xl border border-slate-800 text-slate-200">
        Mensaje
      </div>
      <div class="flex justify-end pt-2">
        <button onclick="cerrarModalAlerta()" class="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition">
          Aceptar y continuar
        </button>
      </div>
    </div>
  </div>

  <!-- MODAL DE CONFIRMACIÓN (DUPLICADOS POR DNI O ENTRADA REPETIDA) -->
  <div id="modal-confirmacion" class="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 hidden">
    <div class="bg-slate-900 border border-amber-600/50 max-w-md w-full rounded-2xl p-6 shadow-2xl space-y-4">
      <div class="flex items-center gap-3">
        <div class="p-3 rounded-xl bg-amber-500/20 text-amber-400 font-bold text-xl">❓</div>
        <div>
          <h3 id="conf-titulo" class="text-base font-bold text-white">Dato Ya Registrado</h3>
          <p class="text-xs text-slate-400">Confirmación requerida</p>
        </div>
      </div>
      <div id="conf-mensaje" class="text-sm bg-slate-950 p-4 rounded-xl border border-slate-800 text-slate-200">
        ¿Estás seguro de realizarlo?
      </div>
      <div class="flex justify-end gap-3 pt-2">
        <button onclick="responderConfirmacion(false)" class="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-bold transition">
          Cancelar
        </button>
        <button onclick="responderConfirmacion(true)" class="px-5 py-2.5 bg-amber-600 hover:bg-amber-500 text-white rounded-xl text-xs font-bold transition">
          Sí, estoy seguro
        </button>
      </div>
    </div>
  </div>

  <div class="max-w-6xl mx-auto space-y-6">

    <!-- Encabezado -->
    <header class="bg-slate-900 border border-slate-800 p-6 rounded-2xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
      <div>
        <span class="text-xs font-mono uppercase bg-indigo-950 text-indigo-400 border border-indigo-800 px-3 py-1 rounded-full">
          Python 3 + SQLite (Validación por DNI y Duplicados)
        </span>
        <h1 class="text-2xl font-bold text-white mt-2">Boletería Cultural - Carga Manual y Emisión</h1>
      </div>
      <button onclick="vaciarBaseDatos()" class="px-4 py-2 bg-rose-950 hover:bg-rose-900 border border-rose-800 text-rose-300 rounded-xl text-xs font-bold transition">
        🗑️ Vaciar Todo a 0
      </button>
    </header>

    <!-- FORMULARIOS DE CARGA MANUAL -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">

      <!-- Formulario 1: Registrar Cliente con DNI -->
      <div class="bg-slate-900 border border-slate-800 p-5 rounded-2xl space-y-4">
        <h2 class="text-sm font-bold text-white flex items-center gap-2">
          <span>👤</span> Paso 1: Cargar Nuevo Cliente
        </h2>
        <form onsubmit="guardarCliente(event)" class="space-y-3">
          <div>
            <label class="block text-xs text-slate-400 mb-1">Nombre y Apellido:</label>
            <input type="text" id="cli-nombre" placeholder="Ej: Brenda Moreno" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500">
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block text-xs text-slate-400 mb-1">DNI (Documento):</label>
              <input type="text" id="cli-dni" placeholder="Ej: 38450123" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500">
            </div>
            <div>
              <label class="block text-xs text-slate-400 mb-1">Correo Electrónico:</label>
              <input type="email" id="cli-email" placeholder="Ej: brenda@email.com" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500">
            </div>
          </div>
          <button type="submit" class="w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition">
            Guardar Cliente en BD
          </button>
        </form>
      </div>

      <!-- Formulario 2: Registrar Evento -->
      <div class="bg-slate-900 border border-slate-800 p-5 rounded-2xl space-y-4">
        <h2 class="text-sm font-bold text-white flex items-center gap-2">
          <span>🎭</span> Paso 2: Cargar Nuevo Evento
        </h2>
        <form onsubmit="guardarEvento(event)" class="space-y-3">
          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block text-xs text-slate-400 mb-1">Nombre Evento:</label>
              <input type="text" id="ev-nombre" placeholder="Ej: El Cascanueces" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-white focus:outline-none focus:border-indigo-500">
            </div>
            <div>
              <label class="block text-xs text-slate-400 mb-1">Sala:</label>
              <input type="text" id="ev-sala" placeholder="Ej: Sala Principal" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-white focus:outline-none focus:border-indigo-500">
            </div>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block text-xs text-slate-400 mb-1">Cupo Máximo:</label>
              <input type="number" id="ev-cupo" placeholder="Ej: 2" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-white focus:outline-none focus:border-indigo-500">
            </div>
            <div>
              <label class="block text-xs text-slate-400 mb-1">Categoría:</label>
              <select id="ev-tipo" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-white">
                <option value="Estándar">Estándar (Tarifa plana)</option>
                <option value="VIP">VIP (+25% por Catering)</option>
              </select>
            </div>
          </div>
          <button type="submit" class="w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition">
            Guardar Evento en BD
          </button>
        </form>
      </div>

    </div>

    <!-- FORMULARIO 3: EMISIÓN DE TICKETS -->
    <div class="bg-slate-900 border border-slate-800 p-6 rounded-2xl space-y-4">
      <h2 class="text-sm font-bold text-white flex items-center gap-2">
        <span>🎟️</span> Paso 3: Emitir Entrada (Aplica Reglas de Consigna 2)
      </h2>
      <form onsubmit="emitirEntrada(event)" class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
        <div>
          <label class="block text-xs text-slate-400 mb-1">Seleccionar Evento:</label>
          <select id="sel-evento" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-white"></select>
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">Seleccionar Cliente (Nombre y DNI):</label>
          <select id="sel-cliente" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-white"></select>
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">Precio Base ($):</label>
          <input type="number" id="inp-precio" placeholder="Ej: 3500" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-white">
        </div>
        <button type="submit" class="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition">
          Confirmar y Emitir
        </button>
      </form>
    </div>

    <!-- TABLAS EN VIVO -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">

      <!-- Tabla Clientes con DNI -->
      <div class="bg-slate-900 border border-slate-800 p-5 rounded-2xl space-y-3">
        <h3 class="text-xs font-bold text-slate-300">Clientes Registrados en BD</h3>
        <div class="overflow-x-auto max-h-48 text-xs font-mono">
          <table class="w-full text-left">
            <thead class="text-slate-400 border-b border-slate-800">
              <tr>
                <th class="p-2">ID</th>
                <th class="p-2">Nombre</th>
                <th class="p-2">DNI</th>
                <th class="p-2">Email</th>
              </tr>
            </thead>
            <tbody id="tabla-clientes" class="divide-y divide-slate-800 text-slate-300">
              <tr><td colspan="4" class="p-3 text-center text-slate-500">Sin clientes cargados aún.</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Tabla Eventos -->
      <div class="bg-slate-900 border border-slate-800 p-5 rounded-2xl space-y-3">
        <h3 class="text-xs font-bold text-slate-300">Eventos y Cupo en BD</h3>
        <div class="overflow-x-auto max-h-48 text-xs font-mono">
          <table class="w-full text-left">
            <thead class="text-slate-400 border-b border-slate-800">
              <tr><th class="p-2">ID</th><th class="p-2">Evento</th><th class="p-2">Tipo</th><th class="p-2">Cupo</th></tr>
            </thead>
            <tbody id="tabla-eventos" class="divide-y divide-slate-800 text-slate-300">
              <tr><td colspan="4" class="p-3 text-center text-slate-500">Sin eventos cargados aún.</td></tr>
            </tbody>
          </table>
        </div>
      </div>

    </div>

    <!-- Tabla Entradas Emitidas -->
    <div class="bg-slate-900 border border-slate-800 p-5 rounded-2xl space-y-3">
      <h3 class="text-xs font-bold text-slate-300">Entradas Emitidas (Historial en BD)</h3>
      <div class="overflow-x-auto max-h-56 text-xs font-mono">
        <table class="w-full text-left">
          <thead class="text-slate-400 border-b border-slate-800">
            <tr>
              <th class="p-2">N° Ticket</th>
              <th class="p-2">Evento</th>
              <th class="p-2">Cliente y DNI</th>
              <th class="p-2">Precio Cobrado</th>
            </tr>
          </thead>
          <tbody id="tabla-entradas" class="divide-y divide-slate-800 text-slate-300">
            <tr><td colspan="4" class="p-4 text-center text-slate-500">No hay tickets emitidos todavía.</td></tr>
          </tbody>
        </table>
      </div>
    </div>

  </div>

  <script>
    let accionPendiente = null;

    function mostrarModalAlerta(mensaje, titulo = "Atención: dato faltante o inválido", esError = true) {
      document.getElementById('modal-titulo').textContent = titulo;
      document.getElementById('modal-mensaje').textContent = mensaje;
      document.getElementById('modal-icono-box').textContent = esError ? "⚠️" : "🎉";
      document.getElementById('modal-alerta').classList.remove('hidden');
    }

    function cerrarModalAlerta() {
      document.getElementById('modal-alerta').classList.add('hidden');
    }

    function solicitarConfirmacion(mensaje, callback) {
      document.getElementById('conf-mensaje').textContent = mensaje;
      accionPendiente = callback;
      document.getElementById('modal-confirmacion').classList.remove('hidden');
    }

    function responderConfirmacion(acepta) {
      document.getElementById('modal-confirmacion').classList.add('hidden');
      if (acepta && accionPendiente) {
        accionPendiente();
      }
      accionPendiente = null;
    }

    async function actualizarPantalla() {
      const res = await fetch('/api/datos');
      const data = await res.json();

      // Desplegable Eventos
      const selEv = document.getElementById('sel-evento');
      if (data.eventos.length === 0) {
        selEv.innerHTML = '<option value="">-- No hay eventos cargados --</option>';
      } else {
        selEv.innerHTML = data.eventos.map(e => 
          `<option value="${e.id}">[#${e.id}] ${e.nombre} (${e.tipo} | Vendidas: ${e.vendidas}/${e.cupo_maximo})</option>`
        ).join('');
      }

      // Desplegable Clientes (Muestra Nombre y DNI)
      const selCl = document.getElementById('sel-cliente');
      if (data.clientes.length === 0) {
        selCl.innerHTML = '<option value="">-- No hay clientes cargados --</option>';
      } else {
        selCl.innerHTML = data.clientes.map(c => 
          `<option value="${c.id}">[#${c.id}] ${c.nombre} (DNI: ${c.dni})</option>`
        ).join('');
      }

      // Tabla Clientes con DNI
      const tbCl = document.getElementById('tabla-clientes');
      if (data.clientes.length === 0) {
        tbCl.innerHTML = '<tr><td colspan="4" class="p-3 text-center text-slate-500">Sin clientes cargados aún.</td></tr>';
      } else {
        tbCl.innerHTML = data.clientes.map(c => 
          `<tr>
            <td class="p-2 font-bold text-slate-400">#${c.id}</td>
            <td class="p-2 text-white font-medium">${c.nombre}</td>
            <td class="p-2 text-indigo-300 font-bold">${c.dni}</td>
            <td class="p-2 text-slate-400">${c.email}</td>
          </tr>`
        ).join('');
      }

      // Tabla Eventos
      const tbEv = document.getElementById('tabla-eventos');
      if (data.eventos.length === 0) {
        tbEv.innerHTML = '<tr><td colspan="4" class="p-3 text-center text-slate-500">Sin eventos cargados aún.</td></tr>';
      } else {
        tbEv.innerHTML = data.eventos.map(e => 
          `<tr>
            <td class="p-2 font-bold text-slate-400">#${e.id}</td>
            <td class="p-2 text-white">${e.nombre}</td>
            <td class="p-2"><span class="px-2 py-0.5 rounded text-[10px] ${e.tipo === 'VIP' ? 'bg-amber-950 text-amber-300 border border-amber-800' : 'bg-slate-800 text-slate-300'}">${e.tipo}</span></td>
            <td class="p-2 font-bold ${e.vendidas >= e.cupo_maximo ? 'text-rose-400' : 'text-emerald-400'}">${e.vendidas}/${e.cupo_maximo}</td>
          </tr>`
        ).join('');
      }

      // Tabla Entradas
      const tbEn = document.getElementById('tabla-entradas');
      if (data.entradas.length === 0) {
        tbEn.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-slate-500">No hay tickets emitidos todavía.</td></tr>';
      } else {
        tbEn.innerHTML = data.entradas.map(t => 
          `<tr class="hover:bg-slate-800/40">
            <td class="p-2 font-bold text-emerald-400">Ticket N° ${t.numero}</td>
            <td class="p-2 text-white">${t.evento}</td>
            <td class="p-2 text-slate-300">${t.cliente}</td>
            <td class="p-2 font-bold text-indigo-300">$${t.precio.toFixed(2)}</td>
          </tr>`
        ).join('');
      }
    }

    // 1. Guardar Cliente con DNI y Control de Duplicados
    async function guardarCliente(e, forzar = false) {
      if (e) e.preventDefault();
      const nombre = document.getElementById('cli-nombre').value;
      const dni = document.getElementById('cli-dni').value;
      const email = document.getElementById('cli-email').value;

      if (!nombre.trim()) {
        mostrarModalAlerta("Te falta el Nombre y Apellido del cliente.");
        return;
      }
      if (!dni.trim()) {
        mostrarModalAlerta("Te falta el DNI (Documento) del cliente.");
        return;
      }
      if (!email.trim()) {
        mostrarModalAlerta("Te falta el Correo Electrónico del cliente.");
        return;
      }

      const res = await fetch('/api/cliente', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ nombre, dni, email, forzar })
      });
      const data = await res.json();

      if (data.status === 'ok') {
        mostrarModalAlerta(data.mensaje, "¡Cliente registrado!", false);
        document.getElementById('cli-nombre').value = '';
        document.getElementById('cli-dni').value = '';
        document.getElementById('cli-email').value = '';
        actualizarPantalla();
      } else if (data.status === 'duplicado') {
        solicitarConfirmacion(
          `El cliente con DNI '${dni}' ya se encuentra registrado. ¿Estás seguro de registrarlo de todos modos?`,
          () => guardarCliente(null, true)
        );
      } else {
        mostrarModalAlerta(data.mensaje);
      }
    }

    // 2. Guardar Evento
    async function guardarEvento(e) {
      e.preventDefault();
      const nombre = document.getElementById('ev-nombre').value;
      const sala = document.getElementById('ev-sala').value;
      const cupo = document.getElementById('ev-cupo').value;
      const tipo = document.getElementById('ev-tipo').value;

      if (!nombre.trim()) {
        mostrarModalAlerta("Te falta el Nombre del evento.");
        return;
      }
      if (!sala.trim()) {
        mostrarModalAlerta("Te falta la Sala o Ubicación del evento.");
        return;
      }
      if (!cupo || parseInt(cupo) <= 0) {
        mostrarModalAlerta("Te falta ingresar un Cupo Máximo válido (debe ser mayor a 0).");
        return;
      }

      const res = await fetch('/api/evento', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ nombre, sala, cupo_maximo: parseInt(cupo), tipo })
      });
      const data = await res.json();

      if (data.status === 'ok') {
        mostrarModalAlerta(data.mensaje, "¡Evento registrado!", false);
        document.getElementById('ev-nombre').value = '';
        document.getElementById('ev-sala').value = '';
        document.getElementById('ev-cupo').value = '';
        actualizarPantalla();
      } else {
        mostrarModalAlerta(data.mensaje);
      }
    }

    // 3. Emitir Entrada
    async function emitirEntrada(e, forzar = false) {
      if (e) e.preventDefault();
      const evento_id = document.getElementById('sel-evento').value;
      const cliente_id = document.getElementById('sel-cliente').value;
      const precio = document.getElementById('inp-precio').value;

      if (!evento_id) {
        mostrarModalAlerta("Te falta seleccionar un Evento. Primero debes crearlo en el Paso 2.");
        return;
      }
      if (!cliente_id) {
        mostrarModalAlerta("Te falta seleccionar un Cliente. Primero debes crearlo en el Paso 1.");
        return;
      }
      if (!precio || parseFloat(precio) <= 0) {
        mostrarModalAlerta("Te falta ingresar el Precio Base (o ingresaste un número menor o igual a 0).");
        return;
      }

      const res = await fetch('/api/vender', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          evento_id: parseInt(evento_id),
          cliente_id: parseInt(cliente_id),
          precio: parseFloat(precio),
          forzar: forzar
        })
      });
      const data = await res.json();

      if (data.status === 'ok') {
        mostrarModalAlerta(data.mensaje, "¡Entrada Emitida con Éxito!", false);
        document.getElementById('inp-precio').value = '';
        actualizarPantalla();
      } else if (data.status === 'duplicado') {
        solicitarConfirmacion(
          data.mensaje,
          () => emitirEntrada(null, true)
        );
      } else {
        mostrarModalAlerta(`[${data.tipo}]: ${data.mensaje}`);
      }
    }

    async function vaciarBaseDatos() {
      if (confirm("¿Estás seguro de que deseas vaciar todas las tablas a 0?")) {
        await fetch('/api/vaciar', { method: 'POST' });
        actualizarPantalla();
      }
    }

    window.onload = actualizarPantalla;
  </script>
</body>
</html>
"""

# ==============================================================================
# 6. RUTAS API (Backend con soporte para DNI)
# ==============================================================================
@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/datos")
def obtener_datos():
    conn = sqlite3.connect("ticketera.db")
    cur = conn.cursor()

    cur.execute("SELECT id, nombre, dni, email FROM clientes ORDER BY id DESC")
    clientes = [{"id": r[0], "nombre": r[1], "dni": r[2], "email": r[3]} for r in cur.fetchall()]

    cur.execute("SELECT id, nombre, sala, cupo_maximo, tipo FROM eventos ORDER BY id DESC")
    eventos = []
    for r in cur.fetchall():
        cur.execute("SELECT COUNT(*) FROM entradas WHERE evento_id = ?", (r[0],))
        vendidas = cur.fetchone()[0]
        eventos.append({"id": r[0], "nombre": r[1], "sala": r[2], "cupo_maximo": r[3], "tipo": r[4], "vendidas": vendidas})

    cur.execute("""
        SELECT e.numero, ev.nombre, c.nombre || ' (DNI: ' || c.dni || ')', e.precio 
        FROM entradas e
        JOIN eventos ev ON e.evento_id = ev.id
        JOIN clientes c ON e.cliente_id = c.id
        ORDER BY e.numero DESC
    """)
    entradas = [{"numero": r[0], "evento": r[1], "cliente": r[2], "precio": r[3]} for r in cur.fetchall()]
    conn.close()

    return jsonify({"clientes": clientes, "eventos": eventos, "entradas": entradas})

@app.route("/api/cliente", methods=["POST"])
def crear_cliente():
    data = request.json
    nombre = data.get("nombre", "")
    dni = data.get("dni", "")
    email = data.get("email", "")
    forzar = data.get("forzar", False)

    try:
        cliente_obj = Cliente(0, nombre, dni, email)
        
        conn = sqlite3.connect("ticketera.db")
        cur = conn.cursor()

        # Detección de duplicado por DNI
        if not forzar:
            cur.execute("SELECT COUNT(*) FROM clientes WHERE dni = ?", (cliente_obj.dni,))
            if cur.fetchone()[0] > 0:
                conn.close()
                return jsonify({"status": "duplicado", "mensaje": "Cliente con este DNI ya registrado."})

        cur.execute("INSERT INTO clientes (nombre, dni, email) VALUES (?, ?, ?)", 
                    (cliente_obj.nombre, cliente_obj.dni, cliente_obj.email))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "mensaje": f"Cliente '{cliente_obj.nombre}' (DNI: {cliente_obj.dni}) guardado correctamente en la BD."})
    except DatoInvalidoError as err:
        return jsonify({"status": "error", "tipo": "DatoInvalidoError", "mensaje": str(err)})

@app.route("/api/evento", methods=["POST"])
def crear_evento():
    data = request.json
    try:
        nombre = data.get("nombre", "")
        sala = data.get("sala", "")
        cupo = int(data.get("cupo_maximo", 0))
        tipo = data.get("tipo", "Estándar")

        if tipo == "VIP":
            evento_obj = EventoVIP(0, nombre, sala, cupo)
        else:
            evento_obj = EventoEstandar(0, nombre, sala, cupo)

        conn = sqlite3.connect("ticketera.db")
        cur = conn.cursor()
        cur.execute("INSERT INTO eventos (nombre, sala, cupo_maximo, tipo) VALUES (?, ?, ?, ?)", 
                    (evento_obj.nombre, evento_obj.sala, evento_obj.cupo_maximo, evento_obj.tipo))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "mensaje": f"Evento '{evento_obj.nombre}' ({evento_obj.tipo}) guardado con cupo de {evento_obj.cupo_maximo} lugares."})
    except (DatoInvalidoError, ValueError) as err:
        return jsonify({"status": "error", "tipo": "DatoInvalidoError", "mensaje": str(err)})

@app.route("/api/vender", methods=["POST"])
def vender():
    data = request.json
    try:
        ev_id = int(data["evento_id"])
        cl_id = int(data["cliente_id"])
        precio = float(data["precio"])
        forzar = data.get("forzar", False)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "tipo": "DatoInvalidoError", "mensaje": "Falta completar los datos de venta correctamente."})

    conn = sqlite3.connect("ticketera.db")
    cur = conn.cursor()

    cur.execute("SELECT nombre, dni, email FROM clientes WHERE id = ?", (cl_id,))
    c_row = cur.fetchone()
    if not c_row:
        conn.close()
        return jsonify({"status": "error", "tipo": "DatoInvalidoError", "mensaje": "El cliente seleccionado no existe."})
    cliente_obj = Cliente(cl_id, c_row[0], c_row[1], c_row[2])

    cur.execute("SELECT nombre, sala, cupo_maximo, tipo FROM eventos WHERE id = ?", (ev_id,))
    e_row = cur.fetchone()
    if not e_row:
        conn.close()
        return jsonify({"status": "error", "tipo": "DatoInvalidoError", "mensaje": "El evento seleccionado no existe."})

    if e_row[3] == "VIP":
        evento_obj = EventoVIP(ev_id, e_row[0], e_row[1], e_row[2])
    else:
        evento_obj = EventoEstandar(ev_id, e_row[0], e_row[1], e_row[2])

    # Reconstrucción de entradas vendidas
    cur.execute("SELECT numero, precio FROM entradas WHERE evento_id = ?", (ev_id,))
    for t_row in cur.fetchall():
        evento_obj.entradas_vendidas.append(Entrada(t_row[0], evento_obj, cliente_obj, t_row[1]))

    # Verificación de entrada duplicada
    if not forzar:
        cur.execute("SELECT COUNT(*) FROM entradas WHERE evento_id = ? AND cliente_id = ?", (ev_id, cl_id))
        if cur.fetchone()[0] > 0:
            conn.close()
            return jsonify({
                "status": "duplicado", 
                "mensaje": f"El cliente {cliente_obj.nombre} (DNI: {cliente_obj.dni}) ya posee una entrada para '{evento_obj.nombre}'. ¿Estás seguro de emitirle otra entrada duplicada?"
            })

    try:
        cur.execute("SELECT COALESCE(MAX(numero), 0) + 1 FROM entradas")
        nuevo_nro = cur.fetchone()[0]

        ticket = evento_obj.vender_entrada(cliente_obj, precio, nuevo_nro)

        cur.execute("INSERT INTO entradas (numero, evento_id, cliente_id, precio) VALUES (?, ?, ?, ?)",
                    (ticket.numero, ev_id, cl_id, ticket.precio))
        conn.commit()
        conn.close()
        return jsonify({
            "status": "ok", 
            "mensaje": f"Ticket N° {ticket.numero} emitido para {cliente_obj.nombre} (DNI: {cliente_obj.dni}) en '{evento_obj.nombre}'. Importe final: ${ticket.precio:.2f}"
        })
    except (DatoInvalidoError, EntradaInvalidaError) as err:
        conn.close()
        return jsonify({"status": "error", "tipo": type(err).__name__, "mensaje": str(err)})

@app.route("/api/vaciar", methods=["POST"])
def vaciar():
    conn = sqlite3.connect("ticketera.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM entradas")
    cur.execute("DELETE FROM eventos")
    cur.execute("DELETE FROM clientes")
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
