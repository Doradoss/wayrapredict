package com.wayrapredict.api.repositories;

import com.wayrapredict.api.entities.Variable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface VariableRepository extends JpaRepository<Variable, Integer> {
    Optional<Variable> findByCodigo(String codigo);
}
