-- =====================================================================
-- WayraPredict — esquema REAL de la base "wayrapredict" (solo estructura, sin datos)
-- Exportado de PostgreSQL 16 con pg_dump --schema-only el 02/11/2026, después de cargar la versión 3.
-- Es solo de referencia: refleja exactamente lo que hay en la base (tablas, restricciones, índices y la
-- vista v_alerta). La carga de la versión 3 NO cambió el esquema: no hay tablas ni columnas nuevas.
-- Coincide con ../../esquema_wayrapredict.sql (v1.4), que ya incluye 'pronostico_meteo' en el CHECK de
-- medicion_diaria.origen; en la base esa restricción se llama ck_medicion_origen (migración v1.3 hecha en pgAdmin).
-- =====================================================================

--
-- PostgreSQL database dump
--

-- Dumped from database version 16.4
-- Dumped by pg_dump version 16.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: categoria_inca; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categoria_inca (
    id_categoria smallint NOT NULL,
    nombre character varying(30) NOT NULL,
    color_hex character(7) NOT NULL,
    inca_min numeric(6,1),
    inca_max numeric(6,1),
    recomendacion text NOT NULL
);


--
-- Name: categoria_inca_id_categoria_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.categoria_inca_id_categoria_seq
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: categoria_inca_id_categoria_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.categoria_inca_id_categoria_seq OWNED BY public.categoria_inca.id_categoria;


--
-- Name: ejecucion_proceso; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ejecucion_proceso (
    id_ejecucion bigint NOT NULL,
    fecha_inicio timestamp without time zone DEFAULT now() NOT NULL,
    fecha_fin timestamp without time zone,
    estado character varying(12) DEFAULT 'en_curso'::character varying NOT NULL,
    mensaje_error text,
    CONSTRAINT ejecucion_proceso_estado_check CHECK (((estado)::text = ANY ((ARRAY['en_curso'::character varying, 'completada'::character varying, 'fallida'::character varying])::text[])))
);


--
-- Name: ejecucion_proceso_id_ejecucion_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ejecucion_proceso_id_ejecucion_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ejecucion_proceso_id_ejecucion_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ejecucion_proceso_id_ejecucion_seq OWNED BY public.ejecucion_proceso.id_ejecucion;


--
-- Name: estacion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.estacion (
    id_estacion integer NOT NULL,
    codigo character varying(20) NOT NULL,
    nombre character varying(120) NOT NULL,
    departamento character varying(60) NOT NULL,
    provincia character varying(60),
    distrito character varying(60),
    este numeric(12,2),
    norte numeric(12,2),
    zona_utm smallint,
    altitud integer,
    activa boolean DEFAULT true NOT NULL
);


--
-- Name: estacion_id_estacion_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.estacion_id_estacion_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: estacion_id_estacion_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.estacion_id_estacion_seq OWNED BY public.estacion.id_estacion;


--
-- Name: medicion_diaria; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.medicion_diaria (
    id_medicion bigint NOT NULL,
    id_estacion integer NOT NULL,
    id_variable integer NOT NULL,
    id_ejecucion bigint,
    fecha date NOT NULL,
    valor numeric(10,3) NOT NULL,
    origen character varying(20) DEFAULT 'estacion'::character varying NOT NULL,
    CONSTRAINT ck_medicion_origen CHECK (((origen)::text = ANY ((ARRAY['estacion'::character varying, 'estacion_vecina'::character varying, 'servicio_meteo'::character varying, 'pronostico_meteo'::character varying])::text[])))
);


--
-- Name: medicion_diaria_id_medicion_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.medicion_diaria_id_medicion_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: medicion_diaria_id_medicion_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.medicion_diaria_id_medicion_seq OWNED BY public.medicion_diaria.id_medicion;


--
-- Name: modelo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.modelo (
    id_modelo integer NOT NULL,
    id_estacion integer NOT NULL,
    id_variable integer NOT NULL,
    version character varying(20) NOT NULL,
    ruta_blob character varying(255) NOT NULL,
    fecha_entrenamiento timestamp without time zone NOT NULL,
    rmse numeric(10,4),
    mae numeric(10,4),
    r2 numeric(6,4),
    vigente boolean DEFAULT false NOT NULL
);


--
-- Name: modelo_id_modelo_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.modelo_id_modelo_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: modelo_id_modelo_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.modelo_id_modelo_seq OWNED BY public.modelo.id_modelo;


--
-- Name: prediccion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prediccion (
    id_prediccion bigint NOT NULL,
    id_modelo integer NOT NULL,
    id_ejecucion bigint NOT NULL,
    fecha_objetivo date NOT NULL,
    valor numeric(10,3) NOT NULL,
    limite_inferior numeric(10,3),
    limite_superior numeric(10,3),
    id_categoria smallint NOT NULL,
    verificado boolean DEFAULT false NOT NULL,
    verificado_por integer,
    fecha_verificacion timestamp without time zone,
    CONSTRAINT prediccion_check CHECK (((verificado AND (verificado_por IS NOT NULL) AND (fecha_verificacion IS NOT NULL)) OR ((NOT verificado) AND (verificado_por IS NULL) AND (fecha_verificacion IS NULL))))
);


--
-- Name: prediccion_id_prediccion_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.prediccion_id_prediccion_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: prediccion_id_prediccion_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.prediccion_id_prediccion_seq OWNED BY public.prediccion.id_prediccion;


--
-- Name: usuario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario (
    id_usuario integer NOT NULL,
    nombres character varying(80) NOT NULL,
    apellidos character varying(80) NOT NULL,
    correo character varying(150) NOT NULL,
    hash_contrasena character varying(255) NOT NULL,
    institucion character varying(150),
    cargo character varying(100),
    rol character varying(25) DEFAULT 'usuario_institucional'::character varying NOT NULL,
    estado character varying(12) DEFAULT 'pendiente'::character varying NOT NULL,
    fecha_registro timestamp without time zone DEFAULT now() NOT NULL,
    aprobado_por integer,
    fecha_aprobacion timestamp without time zone,
    CONSTRAINT usuario_estado_check CHECK (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'aprobado'::character varying, 'rechazado'::character varying])::text[]))),
    CONSTRAINT usuario_rol_check CHECK (((rol)::text = ANY ((ARRAY['administrador'::character varying, 'usuario_institucional'::character varying])::text[])))
);


--
-- Name: usuario_id_usuario_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usuario_id_usuario_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuario_id_usuario_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usuario_id_usuario_seq OWNED BY public.usuario.id_usuario;


--
-- Name: variable; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.variable (
    id_variable integer NOT NULL,
    codigo character varying(30) NOT NULL,
    nombre character varying(80) NOT NULL,
    tipo character varying(20) NOT NULL,
    unidad character varying(20) NOT NULL,
    eca_24h numeric(8,2),
    oms_24h numeric(8,2),
    vuec numeric(8,2),
    CONSTRAINT variable_tipo_check CHECK (((tipo)::text = ANY ((ARRAY['contaminante'::character varying, 'meteorologica'::character varying])::text[])))
);


--
-- Name: v_alerta; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_alerta AS
 SELECT p.id_prediccion,
    e.codigo AS estacion,
    e.departamento,
    v.codigo AS contaminante,
    p.fecha_objetivo,
    ref.fecha_referencia,
    (p.fecha_objetivo - ref.fecha_referencia) AS dias_desde_referencia,
    p.valor,
    round(((p.valor * (100)::numeric) / v.eca_24h), 1) AS valor_inca,
    c.nombre AS categoria_inca,
    c.color_hex,
    (p.valor > v.eca_24h) AS supera_eca,
        CASE
            WHEN (p.fecha_objetivo > ref.fecha_referencia) THEN 'vigente'::text
            ELSE 'finalizada'::text
        END AS estado
   FROM (((((public.prediccion p
     JOIN public.modelo m ON ((m.id_modelo = p.id_modelo)))
     JOIN public.estacion e ON ((e.id_estacion = m.id_estacion)))
     JOIN public.variable v ON ((v.id_variable = m.id_variable)))
     JOIN public.categoria_inca c ON ((c.id_categoria = p.id_categoria)))
     JOIN LATERAL ( SELECT max(md.fecha) AS fecha_referencia
           FROM public.medicion_diaria md
          WHERE ((md.id_estacion = m.id_estacion) AND (md.id_variable = m.id_variable) AND ((md.origen)::text = 'estacion'::text))) ref ON (true))
  WHERE ((c.nombre)::text <> 'Buena'::text);


--
-- Name: variable_id_variable_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.variable_id_variable_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: variable_id_variable_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.variable_id_variable_seq OWNED BY public.variable.id_variable;


--
-- Name: categoria_inca id_categoria; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categoria_inca ALTER COLUMN id_categoria SET DEFAULT nextval('public.categoria_inca_id_categoria_seq'::regclass);


--
-- Name: ejecucion_proceso id_ejecucion; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ejecucion_proceso ALTER COLUMN id_ejecucion SET DEFAULT nextval('public.ejecucion_proceso_id_ejecucion_seq'::regclass);


--
-- Name: estacion id_estacion; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estacion ALTER COLUMN id_estacion SET DEFAULT nextval('public.estacion_id_estacion_seq'::regclass);


--
-- Name: medicion_diaria id_medicion; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medicion_diaria ALTER COLUMN id_medicion SET DEFAULT nextval('public.medicion_diaria_id_medicion_seq'::regclass);


--
-- Name: modelo id_modelo; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.modelo ALTER COLUMN id_modelo SET DEFAULT nextval('public.modelo_id_modelo_seq'::regclass);


--
-- Name: prediccion id_prediccion; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prediccion ALTER COLUMN id_prediccion SET DEFAULT nextval('public.prediccion_id_prediccion_seq'::regclass);


--
-- Name: usuario id_usuario; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario ALTER COLUMN id_usuario SET DEFAULT nextval('public.usuario_id_usuario_seq'::regclass);


--
-- Name: variable id_variable; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.variable ALTER COLUMN id_variable SET DEFAULT nextval('public.variable_id_variable_seq'::regclass);


--
-- Name: categoria_inca categoria_inca_nombre_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categoria_inca
    ADD CONSTRAINT categoria_inca_nombre_key UNIQUE (nombre);


--
-- Name: categoria_inca categoria_inca_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categoria_inca
    ADD CONSTRAINT categoria_inca_pkey PRIMARY KEY (id_categoria);


--
-- Name: ejecucion_proceso ejecucion_proceso_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ejecucion_proceso
    ADD CONSTRAINT ejecucion_proceso_pkey PRIMARY KEY (id_ejecucion);


--
-- Name: estacion estacion_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estacion
    ADD CONSTRAINT estacion_codigo_key UNIQUE (codigo);


--
-- Name: estacion estacion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estacion
    ADD CONSTRAINT estacion_pkey PRIMARY KEY (id_estacion);


--
-- Name: medicion_diaria medicion_diaria_id_estacion_id_variable_fecha_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medicion_diaria
    ADD CONSTRAINT medicion_diaria_id_estacion_id_variable_fecha_key UNIQUE (id_estacion, id_variable, fecha);


--
-- Name: medicion_diaria medicion_diaria_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medicion_diaria
    ADD CONSTRAINT medicion_diaria_pkey PRIMARY KEY (id_medicion);


--
-- Name: modelo modelo_id_estacion_id_variable_version_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.modelo
    ADD CONSTRAINT modelo_id_estacion_id_variable_version_key UNIQUE (id_estacion, id_variable, version);


--
-- Name: modelo modelo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.modelo
    ADD CONSTRAINT modelo_pkey PRIMARY KEY (id_modelo);


--
-- Name: prediccion prediccion_id_ejecucion_id_modelo_fecha_objetivo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prediccion
    ADD CONSTRAINT prediccion_id_ejecucion_id_modelo_fecha_objetivo_key UNIQUE (id_ejecucion, id_modelo, fecha_objetivo);


--
-- Name: prediccion prediccion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prediccion
    ADD CONSTRAINT prediccion_pkey PRIMARY KEY (id_prediccion);


--
-- Name: usuario usuario_correo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_correo_key UNIQUE (correo);


--
-- Name: usuario usuario_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_pkey PRIMARY KEY (id_usuario);


--
-- Name: variable variable_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.variable
    ADD CONSTRAINT variable_codigo_key UNIQUE (codigo);


--
-- Name: variable variable_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.variable
    ADD CONSTRAINT variable_pkey PRIMARY KEY (id_variable);


--
-- Name: ix_prediccion_consulta; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_prediccion_consulta ON public.prediccion USING btree (id_modelo, fecha_objetivo);


--
-- Name: ux_modelo_vigente; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_modelo_vigente ON public.modelo USING btree (id_estacion, id_variable) WHERE vigente;


--
-- Name: medicion_diaria medicion_diaria_id_ejecucion_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medicion_diaria
    ADD CONSTRAINT medicion_diaria_id_ejecucion_fkey FOREIGN KEY (id_ejecucion) REFERENCES public.ejecucion_proceso(id_ejecucion);


--
-- Name: medicion_diaria medicion_diaria_id_estacion_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medicion_diaria
    ADD CONSTRAINT medicion_diaria_id_estacion_fkey FOREIGN KEY (id_estacion) REFERENCES public.estacion(id_estacion);


--
-- Name: medicion_diaria medicion_diaria_id_variable_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medicion_diaria
    ADD CONSTRAINT medicion_diaria_id_variable_fkey FOREIGN KEY (id_variable) REFERENCES public.variable(id_variable);


--
-- Name: modelo modelo_id_estacion_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.modelo
    ADD CONSTRAINT modelo_id_estacion_fkey FOREIGN KEY (id_estacion) REFERENCES public.estacion(id_estacion);


--
-- Name: modelo modelo_id_variable_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.modelo
    ADD CONSTRAINT modelo_id_variable_fkey FOREIGN KEY (id_variable) REFERENCES public.variable(id_variable);


--
-- Name: prediccion prediccion_id_categoria_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prediccion
    ADD CONSTRAINT prediccion_id_categoria_fkey FOREIGN KEY (id_categoria) REFERENCES public.categoria_inca(id_categoria);


--
-- Name: prediccion prediccion_id_ejecucion_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prediccion
    ADD CONSTRAINT prediccion_id_ejecucion_fkey FOREIGN KEY (id_ejecucion) REFERENCES public.ejecucion_proceso(id_ejecucion);


--
-- Name: prediccion prediccion_id_modelo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prediccion
    ADD CONSTRAINT prediccion_id_modelo_fkey FOREIGN KEY (id_modelo) REFERENCES public.modelo(id_modelo);


--
-- Name: prediccion prediccion_verificado_por_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prediccion
    ADD CONSTRAINT prediccion_verificado_por_fkey FOREIGN KEY (verificado_por) REFERENCES public.usuario(id_usuario);


--
-- Name: usuario usuario_aprobado_por_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_aprobado_por_fkey FOREIGN KEY (aprobado_por) REFERENCES public.usuario(id_usuario);


--
-- PostgreSQL database dump complete
--

