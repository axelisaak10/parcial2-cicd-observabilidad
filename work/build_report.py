from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

root=Path.cwd(); out=root/'outputs'; work=root/'work'; out.mkdir(exist_ok=True); work.mkdir(exist_ok=True)
# Generate a simple, original architecture figure.
W,H=1600,670
im=Image.new('RGB',(W,H),'#F3F6F4'); d=ImageDraw.Draw(im)
font_path='C:/Windows/Fonts/arial.ttf'; bold_path='C:/Windows/Fonts/arialbd.ttf'
try: f=ImageFont.truetype(font_path,25); fb=ImageFont.truetype(bold_path,27); small=ImageFont.truetype(font_path,19)
except: f=fb=small=ImageFont.load_default()
def box(x,y,w,h,title,sub,color='#FFFFFF'):
 d.rounded_rectangle((x,y,x+w,y+h),radius=20,fill=color,outline='#CAD6CF',width=3)
 d.text((x+20,y+21),title,font=fb,fill='#183349')
 for j,line in enumerate(sub.split('\n')): d.text((x+20,y+67+j*29),line,font=small,fill='#5D7068')
def arrow(x1,y1,x2,y2,label=''):
 d.line((x1,y1,x2,y2),fill='#5C8267',width=5)
 d.polygon([(x2,y2),(x2-14,y2-9),(x2-14,y2+9)],fill='#5C8267')
 if label:d.text(((x1+x2)//2-50,(y1+y2)//2-30),label,font=small,fill='#476B53')
box(40,230,245,150,'GitHub Actions','Commit → pruebas\nFallo → bloquea despliegue','#E9F0EB')
box(375,70,245,145,'Pruebas','pytest · API\nPlaywright · UI')
box(375,410,245,145,'Docker Hub','Imágenes por commit\nAPI + frontend')
box(760,230,260,150,'AWS EC2','Frontend + API\nDocker Compose','#E9F0EB')
box(1175,70,280,145,'OpenTelemetry','Logs · métricas\nTrazas · host metrics')
box(1175,410,280,145,'OpenObserve','Eventos CI/CD\nExploración y tableros','#E9F0EB')
arrow(285,270,370,160,'ejecuta'); arrow(285,330,370,480,'si aprueba'); arrow(620,480,755,340,'pull + arranque'); arrow(1020,270,1170,155,'OTLP'); arrow(1020,340,1170,475,'CI + host')
fig1=work/'figura-arquitectura.png'; im.save(fig1)

# Figure 2: quality gate sequence
im2=Image.new('RGB',(1600,480),'#F3F6F4'); d=ImageDraw.Draw(im2)
steps=[('1','Commit','Push a main'),('2','pytest','API responde'),('3','Playwright','UI agrega y completa'),('4','Publicación','Tags con SHA'),('5','EC2','Compose actualiza')]
for i,(n,t,s) in enumerate(steps):
 x=50+i*310
 d.ellipse((x+70,65,x+132,127),fill='#294E41'); d.text((x+93,78),n,font=fb,fill='white')
 d.rounded_rectangle((x,155,x+240,310),radius=18,fill='white',outline='#CAD6CF',width=3)
 d.text((x+20,180),t,font=fb,fill='#183349'); d.text((x+20,230),s,font=small,fill='#5D7068')
 if i<4:
  d.line((x+245,230,x+300,230),fill='#5C8267',width=5); d.polygon([(x+300,230),(x+286,221),(x+286,239)],fill='#5C8267')
fig2=work/'figura-pipeline.png'; im2.save(fig2)

D=Document(); sec=D.sections[0]; sec.top_margin=Inches(.7); sec.bottom_margin=Inches(.7); sec.left_margin=Inches(.85); sec.right_margin=Inches(.85)
styles=D.styles
styles['Normal'].font.name='Arial'; styles['Normal'].font.size=Pt(10.5); styles['Normal'].font.color.rgb=RGBColor(42,54,52)
styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'),'Arial')
styles['Normal'].paragraph_format.space_after=Pt(7); styles['Normal'].paragraph_format.line_spacing=1.12
for sty,size,color in [('Title',29,'183349'),('Heading 1',18,'183349'),('Heading 2',13,'42654D')]:
 s=styles[sty]; s.font.name='Arial'; s.font.size=Pt(size); s.font.bold=True; s.font.color.rgb=RGBColor.from_string(color)
 s._element.rPr.rFonts.set(qn('w:eastAsia'),'Arial')
# Header and footer
header=sec.header.paragraphs[0]; header.text='PROYECTO PARCIAL 2  /  ARQUITECTURA CI/CD'; header.alignment=WD_ALIGN_PARAGRAPH.RIGHT
header.runs[0].font.name='Arial'; header.runs[0].font.size=Pt(8); header.runs[0].font.color.rgb=RGBColor(100,122,108)
footer=sec.footer.paragraphs[0]; footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=footer.add_run('Informe técnico · 23 de noviembre de 2026'); r.font.size=Pt(8); r.font.color.rgb=RGBColor(100,122,108)
# Cover
p=D.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(80)
r=p.add_run('［NOMBRE DE LA INSTITUCIÓN］'); r.bold=True; r.font.size=Pt(14); r.font.color.rgb=RGBColor(78,111,83)
p=D.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(28)
r=p.add_run('INGENIERÍA / DESARROLLO DE SOFTWARE'); r.font.size=Pt(10); r.font.color.rgb=RGBColor(100,122,108)
p=D.add_paragraph(style='Title'); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(36)
p.add_run('Arquitectura de entrega continua\npruebas automatizadas y observabilidad')
p=D.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(12)
r=p.add_run('Proyecto Parcial 2'); r.font.size=Pt(16); r.font.color.rgb=RGBColor(78,111,83)
for label,val in [('Asignatura','［Nombre de la asignatura］'),('Estudiante','［Nombre del estudiante］'),('Docente','［Nombre del docente］'),('Grupo','［Grupo］'),('Fecha','23 de noviembre de 2026')]:
 p=D.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after=Pt(5)
 r=p.add_run(label+': '); r.bold=True; r.font.size=Pt(10)
 r=p.add_run(val); r.font.size=Pt(10)
D.add_page_break()

def para(text):
 p=D.add_paragraph(text); p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY; return p
def bullet(text):
 p=D.add_paragraph(style='List Bullet'); p.add_run(text); p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY; return p
def caption(text):
 p=D.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(4); p.paragraph_format.space_after=Pt(12)
 r=p.add_run(text); r.italic=True; r.font.size=Pt(9); r.font.color.rgb=RGBColor(87,104,93)
def heading(text,level=1): D.add_heading(text,level=level)
heading('Resumen ejecutivo')
para('Este informe presenta una aplicación web de demostración y una arquitectura de integración y entrega continua para AWS EC2. El repositorio contiene una interfaz web, una API FastAPI, pruebas automatizadas con pytest y Playwright, publicación de imágenes Docker condicionada a la aprobación de las pruebas, configuración de OpenTelemetry y un colector hacia OpenObserve. El código y la suite local se prepararon en el workspace. El repositorio remoto de GitHub puede publicarse desde la sesión autenticada; la creación de EC2 y la publicación en Docker Hub dependen de accesos y secretos que no están configurados en el equipo, por lo que este informe identifica esos pasos como pendientes y no afirma que haya un servidor desplegado.')
heading('1. Introducción')
para('Los cambios frecuentes de software requieren validaciones repetibles y despliegues trazables. Este proyecto integra pruebas de API y de navegador en GitHub Actions y coloca el despliegue detrás de una barrera de calidad: la publicación y actualización de EC2 sólo continúa si pytest y Playwright terminan correctamente. OpenTelemetry transporta señales operativas a OpenObserve, mientras el workflow registra resultados de pruebas y despliegues con commit, rama, usuario ejecutor e identificador de corrida.')
heading('2. Objetivo y alcance')
para('Implementar una aplicación demostrativa de frontend y backend, automatizar su validación integral, preparar la publicación de contenedores, definir la actualización remota de EC2 y centralizar telemetría de aplicación, servidor y pipeline. La aplicación es una lista de tareas educativa y mantiene sus datos en memoria, por lo que no está destinada a conservar información después de reiniciar el proceso.')
heading('3. Arquitectura propuesta')
para('GitHub Actions ejecuta pruebas en cada cambio a main y en pull requests. Cuando las pruebas pasan en main, construye imágenes versionadas con el SHA, las publica en Docker Hub, copia la configuración de Compose a EC2 y ejecuta la actualización por SSH. La aplicación y las métricas del host llegan al OpenTelemetry Collector; el workflow envía eventos JSON a OpenObserve.')
p=D.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run().add_picture(str(fig1),width=Inches(6.75)); caption('Figura 1. Componentes de la arquitectura y flujo de señales.')
heading('4. Implementación')
heading('4.1 Frontend y API',2)
para('El frontend permite crear y completar tareas y presenta el estado de salud de la API. FastAPI expone /health, /api/tasks y /api/tasks/{id}. El middleware registra método, ruta, código HTTP y duración. Las métricas HTTP incluyen conteo y latencia con atributos de método, ruta y código de respuesta. OpenTelemetry auto-instrumenta FastAPI para emitir trazas.')
heading('4.2 Pruebas automatizadas',2)
para('pytest valida el endpoint de salud, creación y finalización de tareas, y rechazo de entradas vacías. Playwright valida que el navegador cargue la interfaz, confirme la conexión con el backend, agregue una tarea y permita completarla. El workflow espera a que /health esté disponible antes de correr la suite.')
heading('4.3 Pipeline de calidad y despliegue',2)
para('El job deploy declara needs: tests y sólo corre para la rama main fuera de pull requests. Una falla deja sin ejecutar la conexión SSH y no publica imágenes nuevas. Si las pruebas pasan, el pipeline publica los tags latest y SHA para frontend y API, transfiere los manifiestos de despliegue y ejecuta docker compose pull/up en EC2.')
p=D.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run().add_picture(str(fig2),width=Inches(6.75)); caption('Figura 2. Secuencia del pipeline y condición de despliegue.')
heading('4.4 Observabilidad')
para('La configuración incluye exportación OTLP de trazas, logs y métricas de aplicación; el collector añade CPU, memoria, disco, filesystem, paginación y red del host Linux. Los eventos del pipeline se guardan en el stream ci_pipeline con commit, rama, actor y run_id. El panel de OpenObserve se enlaza de forma privada por túnel SSH. Los tableros y reglas de alerta se configuran desde la interfaz al iniciar el servidor.')
para('Una instancia EC2 virtual normalmente no expone temperatura física del host al sistema invitado. La configuración recopila métricas Linux disponibles, pero no se atribuye una medición de temperatura inexistente. Para mostrar temperatura real se necesita una fuente de datos del proveedor o sensor disponible.')
heading('5. Criterios de aceptación')
t=D.add_table(rows=1,cols=3); t.style='Light Shading Accent 1'; t.autofit=False
for c,txt in zip(t.rows[0].cells,['Criterio','Implementación','Estado actual']): c.text=txt
rows=[('Fallo de pruebas bloquea EC2','Deploy depende de tests aprobados','Definido en workflow; falta ejecutar en remoto'),('Commit válido publica y despliega','Imágenes por SHA y SSH a Compose','Configurado; falta Docker Hub y EC2'),('OpenObserve recibe CI y telemetría','JSON del workflow + OTLP','Configuración preparada; instancia no creada'),('Métricas de infraestructura y dashboard','Collector hostmetrics + panel manual','CPU/memoria/red/disco preparados; sin temperatura fiable')]
for row in rows:
 cells=t.add_row().cells
 for c,txt in zip(cells,row): c.text=txt
 for c in cells:
  for p in c.paragraphs: p.paragraph_format.space_after=Pt(4)
heading('6. Ejecución y validación')
para('La suite se ejecuta con python -m venv .venv, pip install -r requirements-dev.txt, playwright install chromium y pytest -q. Se intentó preparar un entorno local; el resultado final de las pruebas de navegador debe confirmarse al terminar la instalación de Chromium. GitHub Actions conserva la verificación como control obligatorio para el despliegue.')
heading('7. Enlaces y accesos')
para('Repositorio GitHub: [se añadirá la URL después de crear y publicar el repositorio].')
para('Servidor EC2 / aplicación: pendiente de crear la instancia y ejecutar el despliegue.')
para('OpenObserve: pendiente de levantar en la instancia EC2. Se accederá por túnel SSH y no se publicará el puerto administrativo directamente en Internet.')
para('Las credenciales deben almacenarse en GitHub Actions Secrets y en el archivo .env protegido del servidor. Este informe no contiene contraseñas, tokens Docker Hub ni claves privadas SSH. Nombres de secrets: DOCKERHUB_USERNAME, DOCKERHUB_TOKEN, EC2_HOST, EC2_USER, EC2_SSH_KEY, OO_URL, OO_USER y OO_PASSWORD.')
heading('8. Conclusiones')
para('El proyecto concreta la aplicación y el flujo de CI/CD solicitado en código reproducible. El control de calidad precede técnicamente al despliegue, y la arquitectura integra señales de aplicación, host y pipeline. La entrega queda lista para publicar en GitHub y completar la nube al proporcionar acceso autorizado a AWS, Docker Hub y valores de configuración. Hasta crear y verificar dichos recursos, la URL del servidor, la imagen publicada y el tablero real permanecen pendientes.')
heading('Referencias técnicas')
for text in ['OpenObserve, ingesta OTLP para logs, métricas y trazas: https://openobserve.ai/docs/ingestion/logs/otlp/','OpenTelemetry Collector, guía de configuración: https://openobserve.ai/opentelemetry/collector/']:
 bullet(text)
# table header styling & repeat rows
for row in t.rows:
 for cell in row.cells:
  tcPr=cell._tc.get_or_add_tcPr(); margins=OxmlElement('w:tcMar')
  for side,val in [('top','100'),('start','110'),('bottom','100'),('end','110')]:
   node=OxmlElement('w:'+side); node.set(qn('w:w'),val); node.set(qn('w:type'),'dxa'); margins.append(node)
  tcPr.append(margins)
for cell in t.rows[0].cells:
 for run in cell.paragraphs[0].runs:
  run.bold=True; run.font.color.rgb=RGBColor(255,255,255)
 tcPr=cell._tc.get_or_add_tcPr(); shd=OxmlElement('w:shd'); shd.set(qn('w:fill'),'244A3E'); tcPr.append(shd)
# properties
D.core_properties.title='Arquitectura de entrega continua, pruebas automatizadas y observabilidad'
D.core_properties.subject='Proyecto Parcial 2'
D.core_properties.author='［Nombre del estudiante］'
path=out/'reporte_proyecto_parcial_2.docx'; D.save(path); print(path)
