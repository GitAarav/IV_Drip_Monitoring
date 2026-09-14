export const initialData = {
  deviceId: "ESP32-IV-001",
  bedId: "BED-101",
  fluidType: "Normal Saline",

  currentWeight: 327,
  initialWeight: 500,

  remainingFluid: 327,

  loadCellFlow: 96.8,
  irFlow: 100.1,
  fusedFlow: 98.4,

  flowUncertainty: 4.2,

  dropFactor: 15.63,

  remainingTime: 199,

  confidence: 94,

  sensorDifference: 3.3,

  status: "NORMAL",
};

export const generateHistory = () => {
  const data = [];

  for (let i = 0; i < 30; i++) {
    const weight = 500 - i * 5.8;

    const loadCellFlow =
      96 + Math.sin(i / 3) * 3;

    const irFlow =
      100 + Math.sin(i / 4) * 4;

    const fusedFlow =
      (loadCellFlow + irFlow) / 2;

    data.push({
      time: `${i} min`,
      weight: Number(weight.toFixed(1)),
      loadCell: Number(loadCellFlow.toFixed(1)),
      ir: Number(irFlow.toFixed(1)),
      fused: Number(fusedFlow.toFixed(1)),
    });
  }

  return data;
};