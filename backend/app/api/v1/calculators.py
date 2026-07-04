from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.services.calculators import (
    CorrectedCalciumInput,
    EgfrInput,
    HomaIrInput,
    InstructionText,
    PreventInput,
    SteroidConversionInput,
    calculate_corrected_calcium,
    calculate_egfr,
    calculate_homa_ir,
    calculate_prevent_ascvd,
    convert_steroid,
)
from app.services.instruction_translations import format_bilingual_instructions, translate_to_kannada

router = APIRouter(prefix="/calculators", tags=["calculators"])


@router.post("/egfr")
def egfr(data: EgfrInput, user=Depends(get_current_user)):
    return calculate_egfr(data)


@router.post("/homa-ir")
def homa_ir(data: HomaIrInput, user=Depends(get_current_user)):
    return calculate_homa_ir(data)


@router.post("/corrected-calcium")
def corrected_calcium(data: CorrectedCalciumInput, user=Depends(get_current_user)):
    return calculate_corrected_calcium(data)


@router.post("/steroid-conversion")
def steroid_conversion(data: SteroidConversionInput, user=Depends(get_current_user)):
    try:
        return convert_steroid(data)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/prevent-ascvd")
def prevent_ascvd(data: PreventInput, user=Depends(get_current_user)):
    return calculate_prevent_ascvd(data)


@router.post("/instruction-bilingual")
def instruction_bilingual(data: InstructionText, user=Depends(get_current_user)):
    text = data.text.strip()
    return {
        "english": text,
        "kannada": translate_to_kannada(text),
        "bilingual": format_bilingual_instructions(text),
    }
