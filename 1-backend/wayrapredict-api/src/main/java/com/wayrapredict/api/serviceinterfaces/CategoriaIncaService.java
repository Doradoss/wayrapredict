package com.wayrapredict.api.serviceinterfaces;

import com.wayrapredict.api.dtos.CategoriaIncaDTO.CategoriaIncaDto;
import com.wayrapredict.api.repositories.CategoriaIncaRepository;
import org.modelmapper.ModelMapper;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class CategoriaIncaService {
    final CategoriaIncaRepository categoriaRepository;

    public CategoriaIncaService(CategoriaIncaRepository categoriaRepository) {
        this.categoriaRepository = categoriaRepository;
    }

    //Lista las categorías del INCA en orden (Buena, Moderada, Mala, Umbral de cuidado)
    public List<CategoriaIncaDto> findAll() {
        ModelMapper modelMapper = new ModelMapper();
        return categoriaRepository.findAll(Sort.by("idCategoria")).stream()
                .map(c -> modelMapper.map(c, CategoriaIncaDto.class)).toList();
    }
}
