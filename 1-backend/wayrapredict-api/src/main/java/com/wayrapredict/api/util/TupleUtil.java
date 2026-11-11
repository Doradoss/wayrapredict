package com.wayrapredict.api.util;

import jakarta.persistence.Tuple;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.time.LocalDateTime;

//Lectura segura de columnas de consultas nativas (Tuple): el driver puede devolver java.sql.Date,
//LocalDate, Integer, Long, BigDecimal, etc. según el tipo SQL; aquí se convierten al tipo del DTO.
public final class TupleUtil {

    private TupleUtil() {
    }

    public static String texto(Tuple t, String alias) {
        Object o = t.get(alias);
        return o == null ? null : o.toString();
    }

    public static Integer entero(Tuple t, String alias) {
        Object o = t.get(alias);
        return o == null ? null : ((Number) o).intValue();
    }

    public static Long largo(Tuple t, String alias) {
        Object o = t.get(alias);
        return o == null ? null : ((Number) o).longValue();
    }

    public static BigDecimal decimal(Tuple t, String alias) {
        Object o = t.get(alias);
        if (o == null) return null;
        return o instanceof BigDecimal b ? b : new BigDecimal(o.toString());
    }

    public static Boolean booleano(Tuple t, String alias) {
        Object o = t.get(alias);
        return o == null ? null : (Boolean) o;
    }

    public static LocalDate fecha(Tuple t, String alias) {
        Object o = t.get(alias);
        if (o == null) return null;
        if (o instanceof LocalDate d) return d;
        if (o instanceof java.sql.Date d) return d.toLocalDate();
        return LocalDate.parse(o.toString());
    }

    public static LocalDateTime fechaHora(Tuple t, String alias) {
        Object o = t.get(alias);
        if (o == null) return null;
        if (o instanceof LocalDateTime d) return d;
        if (o instanceof Timestamp ts) return ts.toLocalDateTime();
        return LocalDateTime.parse(o.toString());
    }
}
