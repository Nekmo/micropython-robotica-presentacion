/*
 * Shared-memory layout between the presentation (main thread) and the
 * simulator worker. Inputs live in an Int32Array; floats are stored
 * multiplied by 1000.
 */
export const IDX = {
    SLEEP: 0,          // Atomics.wait target, never written
    TOUCH: 1, TX: 2, TY: 3,
    PWR: 4,
    HEAD0: 5, HEAD1: 6, HEAD2: 7,
    AX: 8, AY: 9, AZ: 10,
    GX: 11, GY: 12, GZ: 13,
    LUX: 14, PROX: 15, BATTERY: 16,
    MIC_ON: 17, MIC_WRITE: 18,
    CAM_FRAME: 19,
    HAND: 20, HAND_X: 21, HAND_Y: 22,
};
export const CONTROL_SLOTS = 32;
export const MIC_RATE = 16000;
export const MIC_SAMPLES = MIC_RATE * 2;          // 2 s ring buffer
export const CAM_W = 320;
export const CAM_H = 240;
export const CAM_BYTES = CAM_W * CAM_H * 2;       // RGB565
