import sqlite3
from abc import ABC, abstractmethod
from flask import Flask, request, jsonify, render_template_string

# ==============================================================================
# 1. EXCEPCIONES PERSONALIZADAS DEL DOMINIO (Consigna 2)
# ==============================================================================
class EntradaInvalidaError(Exception):
    """Regla de negocio: Sin cupo o duplicado."""
    pass

class DatoInvalidoError(Exception):
    """Regla de validación: Precios o campos incorrectos."""
    pass


# ==============================================================================
# 2. INTERFAZ Reportable (Consigna 2)
# ==============================================================================
class Reportable(ABC):
    @abstractmethod
    def generar_resumen(self) -> dict:
        """Contrato formal sin estado propio."""
        pass


# ==============================================================================
# 3. MODELO ORIENTADO A OBJETOS (Consigna 2)
# ==============================================================================
class Cliente:
    def __init__(self, id_cliente: int, nombre: str, email: str):
        if not nombre or not nombre.strip():
            raise DatoInvalidoError("El nombre del cliente no puede estar vacío.")
        self.id_cliente = id_cliente
        self.nombre = nombre
        self.email = email


class EventoBase(Reportable, ABC):
    """Clase base abstracta. No puede ser instanciada directamente."""
    def __init__(self, id_evento: int, nombre: str, sala: str, cupo_maximo: int, tipo: str):
        self.id_evento = id_evento
        self.nombre = nombre
        self.sala = sala
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
        # Validación con raise (Consigna 2)
        if precio_base <= 0:
            raise DatoInvalidoError(f"El precio base (${precio_base}) debe ser mayor a 0.")

        if not self.tiene_cupo_disponible():
            raise EntradaInvalidaError(f"No hay cupo disponible para '{self.nombre}' (Máx: {self.cupo_maximo}).")

        # Cálculo polimórfico
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
        return precio_base * 1.25  # +25% por servicio preferencial


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
            "cliente": self.cliente.nombre,
            "precio": self.precio
        }


# ==============================================================================
# 4. BASE DE DATOS SQLITE (Inicialización y Persistencia)
# ==============================================================================
def init_db():
    conn = sqlite3.connect("ticketera.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            email TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY,
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
    
    # Cargar datos de prueba si la base está vacía
    cur.execute("SELECT COUNT(*) FROM eventos")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO clientes VALUES (1, 'Brenda Moreno', 'brenda@email.com')")
        cur.execute("INSERT INTO clientes VALUES (2, 'Maximiliano Gonzalez', 'mgonzalez@email.com')")
        cur.execute("INSERT INTO clientes VALUES (3, 'Ehimy Ahumada', 'ehimy@email.com')")

        # Evento 1 Estándar (Cupo de 1 para probar la excepción de cupo)
        cur.execute("INSERT INTO eventos VALUES (101, 'El Fantasma de la Ópera', 'Sala Principal', 1, 'Estándar')")
        # Evento 2 VIP
        cur.execute("INSERT INTO eventos VALUES (102, 'Gala Lírica VIP', 'Sala Premium', 5, 'VIP')")
        conn.commit()
    conn.close()

init_db()


# ==============================================================================
# 5. APLICACIÓN WEB FLASK
# ==============================================================================
app = Flask(__name__)

# Template HTML administrativo integrado en un solo archivo
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ticketera Pro - Sistema Administrativo</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 font-sans p-4 md:p-8">
  <div class="max-w-6xl mx-auto space-y-6">

    <!-- Encabezado -->
    <header class="flex flex-col md:flex-row justify-between items-start md:items-center bg-slate-900 border border-slate-800 p-6 rounded-2xl gap-4">
      <div>
        <span class="text-xs font-mono uppercase tracking-wider text-indigo-400 bg-indigo-950/60 border border-indigo-800 px-3 py-1 rounded-full">
          Python 3 + Flask + SQLite (Consigna 2)
        </span>
        <h1 class="text-2xl font-bold text-white mt-2">Sistema Administrativo de Boletos Culturales</h1>
      </div>
      <button onclick="cargarDatos()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-xs font-semibold rounded-xl border border-slate-700 transition">
        🔄 Actualizar Datos
      </button>
    </header>

    <!-- Pruebas rápidas de Consigna 2 -->
    <div class="bg-slate-900/90 border border-slate-800 p-5 rounded-2xl space-y-3">
      <h2 class="text-sm font-semibold text-slate-300">Pruebas Evaluativas de Consigna 2 (1 Clic)</h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
        <button onclick="probar('feliz')" class="p-3 bg-emerald-950/40 hover:bg-emerald-900/60 border border-emerald-800/80 rounded-xl text-left transition">
          <div class="text-emerald-400 font-bold text-xs">1. Camino Feliz</div>
          <div class="text-[11px] text-slate-400">Venta VIP con +25%</div>
        </button>
        <button onclick="probar('precio_invalido')" class="p-3 bg-rose-950/40 hover:bg-rose-900/60 border border-rose-800/80 rounded-xl text-left transition">
          <div class="text-rose-400 font-bold text-xs">2. DatoInvalidoError</div>
          <div class="text-[11px] text-slate-400">Precio negativo (-$500)</div>
        </button>
        <button onclick="probar('sin_cupo')" class="p-3 bg-amber-950/40 hover:bg-amber-900/60 border border-amber-800/80 rounded-xl text-left transition">
          <div class="text-amber-400 font-bold text-xs">3. EntradaInvalidaError</div>
          <div class="text-[11px] text-slate-400">Superar cupo de sala</div>
        </button>
        <button onclick="probar('abstracta')" class="p-3 bg-indigo-950/40 hover:bg-indigo-900/60 border border-indigo-800/80 rounded-xl text-left transition">
          <div class="text-indigo-400 font-bold text-xs">4. Clase Abstracta</div>
          <div class="text-[11px] text-slate-400">TypeError en EventoBase</div>
        </button>
      </div>
    </div>

    <!-- Terminal de Logs / Respuestas -->
    <div class="bg-black/80 border border-slate-800 rounded-2xl p-4 font-mono text-xs">
      <div class="text-slate-500 mb-2">// Registro de ejecución (try/except en backend Python):</div>
      <div id="terminal" class="text-slate-300 space-y-1">Esperando acción...</div>
    </div>

    <!-- Panel de Emisión Manual y Base de Datos -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      
      <!-- Formulario de Venta -->
      <div class="bg-slate-900 border border-slate-800 p-5 rounded-2xl space-y-4">
        <h3 class="font-semibold text-white text-sm">Punto de Venta (POS)</h3>
        <form onsubmit="emitirManual(event)" class="space-y-3">
          <div>
            <label class="block text-xs text-slate-400 mb-1">Evento:</label>
            <select id="sel-evento" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-white"></select>
          </div>
          <div>
            <label class="block text-xs text-slate-400 mb-1">Cliente:</label>
            <select id="sel-cliente" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-white"></select>
          </div>
          <div>
            <label class="block text-xs text-slate-400 mb-1">Precio Base ($):</label>
            <input type="number" id="inp-precio" value="3000" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-white">
          </div>
          <button type="submit" class="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl text-xs transition">
            Emitir Entrada (Backend Python)
          </button>
        </form>
      </div>

      <!-- Tablas de Base de Datos SQLite -->
      <div class="lg:col-span-2 bg-slate-900 border border-slate-800 p-5 rounded-2xl space-y-4">
        <h3 class="font-semibold text-white text-sm">Base de Datos SQLite (Entradas Emitidas)</h3>
        <div class="overflow-x-auto max-h-64">
          <table class="w-full text-left text-xs font-mono">
            <thead class="text-slate-400 border-b border-slate-800">
              <tr>
                <th class="p-2">N° Ticket</th>
                <th class="p-2">Evento</th>
                <th class="p-2">Cliente</th>
                <th class="p-2">Precio Final</th>
              </tr>
            </thead>
            <tbody id="tabla-entradas" class="divide-y divide-slate-800 text-slate-300">
              <tr><td colspan="4" class="p-2 text-slate-500">Cargando datos...</td></tr>
            </tbody>
          </table>
        </div>
      </div>

    </div>

  </div>

  <script>
    async function cargarDatos() {
      const res = await fetch('/api/datos');
      const data = await res.json();
      
      const selEv = document.getElementById('sel-evento');
      selEv.innerHTML = data.eventos.map(e => 
        `<option value="${e.id}">[#${e.id}] ${e.nombre} (${e.tipo} - Vendidas: ${e.vendidas}/${e.cupo_maximo})</option>`
      ).join('');

      const selCl = document.getElementById('sel-cliente');
      selCl.innerHTML = data.clientes.map(c => 
        `<option value="${c.id}">[#${c.id}] ${c.nombre}</option>`
      ).join('');

      const tabla = document.getElementById('tabla-entradas');
      if (data.entradas.length === 0) {
        tabla.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-slate-500">No hay entradas emitidas todavía.</td></tr>';
      } else {
        tabla.innerHTML = data.entradas.map(t => 
          `<tr class="hover:bg-slate-800/40">
            <td class="p-2 text-emerald-400 font-bold">Ticket N° ${t.numero}</td>
            <td class="p-2 text-white">${t.evento}</td>
            <td class="p-2">${t.cliente}</td>
            <td class="p-2 font-bold text-indigo-300">$${t.precio.toFixed(2)}</td>
          </tr>`
        ).join('');
      }
    }

    async function probar(caso) {
      const res = await fetch(`/api/prueba?caso=${caso}`);
      const data = await res.json();
      const term = document.getElementById('terminal');
      
      if (data.status === 'ok') {
        term.innerHTML = `<span class="text-emerald-400 font-bold">✔ [ÉXITO]</span> ${data.mensaje}`;
      } else {
        term.innerHTML = `<span class="text-rose-400 font-bold">🛡 [EXCEPT CAPTURADO]:</span> <span class="text-rose-300">${data.tipo}: ${data.mensaje}</span>`;
      }
      cargarDatos();
    }

    async function emitirManual(e) {
      e.preventDefault();
      const body = {
        evento_id: document.getElementById('sel-evento').value,
        cliente_id: document.getElementById('sel-cliente').value,
        precio: parseFloat(document.getElementById('inp-precio').value)
      };

      const res = await fetch('/api/vender', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body)
      });
      const data = await res.json();
      const term = document.getElementById('terminal');

      if (data.status === 'ok') {
        term.innerHTML = `<span class="text-emerald-400 font-bold">✔ [ÉXITO]:</span> ${data.mensaje}`;
      } else {
        term.innerHTML = `<span class="text-amber-400 font-bold">🛡 [EXCEPCIÓN CAPTURADA]:</span> ${data.tipo}: ${data.mensaje}`;
      }
      cargarDatos();
    }

    window.onload = cargarDatos;
  </script>
</body>
</html>
"""

# ==============================================================================
# 6. RUTAS API (Endpoints REST en Python)
# ==============================================================================
@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/datos")
def obtener_datos():
    conn = sqlite3.connect("ticketera.db")
    cur = conn.cursor()
    
    cur.execute("SELECT id, nombre, email FROM clientes")
    clientes = [{"id": r[0], "nombre": r[1], "email": r[2]} for r in cur.fetchall()]

    cur.execute("SELECT id, nombre, sala, cupo_maximo, tipo FROM eventos")
    eventos = []
    for r in cur.fetchall():
        cur.execute("SELECT COUNT(*) FROM entradas WHERE evento_id = ?", (r[0],))
        vendidas = cur.fetchone()[0]
        eventos.append({"id": r[0], "nombre": r[1], "sala": r[2], "cupo_maximo": r[3], "tipo": r[4], "vendidas": vendidas})

    cur.execute("""
        SELECT e.numero, ev.nombre, c.nombre, e.precio 
        FROM entradas e
        JOIN eventos ev ON e.evento_id = ev.id
        JOIN clientes c ON e.cliente_id = c.id
        ORDER BY e.numero DESC
    """)
    entradas = [{"numero": r[0], "evento": r[1], "cliente": r[2], "precio": r[3]} for r in cur.fetchall()]
    conn.close()

    return jsonify({"clientes": clientes, "eventos": eventos, "entradas": entradas})

@app.route("/api/vender", methods=["POST"])
def vender():
    data = request.json
    ev_id = int(data["evento_id"])
    cl_id = int(data["cliente_id"])
    precio = float(data["precio"])

    conn = sqlite3.connect("ticketera.db")
    cur = conn.cursor()

    cur.execute("SELECT nombre, email FROM clientes WHERE id = ?", (cl_id,))
    c_row = cur.fetchone()
    cliente_obj = Cliente(cl_id, c_row[0], c_row[1])

    cur.execute("SELECT nombre, sala, cupo_maximo, tipo FROM eventos WHERE id = ?", (ev_id,))
    e_row = cur.fetchone()
    
    # Reconstrucción de objetos polimórficos
    if e_row[3] == "VIP":
        evento_obj = EventoVIP(ev_id, e_row[0], e_row[1], e_row[2])
    else:
        evento_obj = EventoEstandar(ev_id, e_row[0], e_row[1], e_row[2])

    cur.execute("SELECT numero, precio FROM entradas WHERE evento_id = ?", (ev_id,))
    for t_row in cur.fetchall():
        evento_obj.entradas_vendidas.append(Entrada(t_row[0], evento_obj, cliente_obj, t_row[1]))

    # Bloque de captura estricto exigido por Consigna 2
    try:
        cur.execute("SELECT COALESCE(MAX(numero), 0) + 1 FROM entradas")
        nuevo_nro = cur.fetchone()[0]
        
        ticket = evento_obj.vender_entrada(cliente_obj, precio, nuevo_nro)
        
        cur.execute("INSERT INTO entradas (numero, evento_id, cliente_id, precio) VALUES (?, ?, ?, ?)",
                    (ticket.numero, ev_id, cl_id, ticket.precio))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "mensaje": f"Ticket N° {ticket.numero} emitido para {cliente_obj.nombre}. Importe final: ${ticket.precio:.2f}"})
    
    except (DatoInvalidoError, EntradaInvalidaError) as err:
        conn.close()
        return jsonify({"status": "error", "tipo": type(err).__name__, "mensaje": str(err)})

@app.route("/api/prueba")
def prueba_rapida():
    caso = request.args.get("caso")

    if caso == "feliz":
        ev = EventoVIP(999, "Gala Lírica VIP", "Sala Premium", 10)
        cl = Cliente(1, "Brenda Moreno", "brenda@email.com")
        t = ev.vender_entrada(cl, 4000.0, 9999)
        return jsonify({"status": "ok", "mensaje": f"Venta exitosa con polimorfismo VIP (+25%): Base $4000 -> Final ${t.precio:.2f}"})

    elif caso == "precio_invalido":
        ev = EventoEstandar(101, "El Fantasma", "Sala A", 10)
        cl = Cliente(2, "Maximiliano Gonzalez", "mg@email.com")
        try:
            ev.vender_entrada(cl, -500.0, 1)
        except DatoInvalidoError as err:
            return jsonify({"status": "error", "tipo": "DatoInvalidoError", "mensaje": str(err)})

    elif caso == "sin_cupo":
        ev = EventoEstandar(101, "El Fantasma", "Sala A", 1) # Cupo 1
        cl1 = Cliente(1, "Brenda", "b@email.com")
        cl2 = Cliente(2, "Maxi", "m@email.com")
        ev.vender_entrada(cl1, 3000.0, 1) # Se llena el cupo
        try:
            ev.vender_entrada(cl2, 3000.0, 2) # Falla
        except EntradaInvalidaError as err:
            return jsonify({"status": "error", "tipo": "EntradaInvalidaError", "mensaje": str(err)})

    elif caso == "abstracta":
        try:
            EventoBase(1, "Evento Genérico", "Sala X", 10, "Abstracto")
        except TypeError as err:
            return jsonify({"status": "error", "tipo": "TypeError", "mensaje": str(err)})

    return jsonify({"status": "ok", "mensaje": "Prueba completada."})


if __name__ == "__main__":
    app.run(debug=True)
